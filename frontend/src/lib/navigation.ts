import type { NavigationTarget, RetrievalEvidenceItem } from './api'

/**
 * D-13's single closed route map (Phase 06.1, plan 06.1-08, RAG-06/RAG-07).
 *
 * The backend's `NavigationTarget` and `RetrievalEvidenceItem` deliberately
 * carry no `url`/`href`/`path`/`link` field -- only a `kind` plus a
 * server-generated entity id. This module is the ONLY place in the frontend
 * that turns those identifiers into a navigable path. Anything that wants to
 * navigate from a Copilot answer imports from here; a second path-builder
 * anywhere else would reintroduce exactly the drift this centralisation
 * exists to prevent, and would reopen the open-redirect surface D-13 closes
 * by construction (no address ever crosses the API boundary -- T-06.1-44).
 */

// Human-readable page names the auto-navigate notice copy interpolates.
export const DESTINATION_LABELS: Record<'document' | 'graph_node', string> = {
  document: 'Knowledge',
  graph_node: 'Blast Radius',
}

// Both `targetId` and `systemId` are server-generated identifiers, not free
// text -- `encodeURIComponent` here is a correctness measure for characters
// that are structurally significant in a URL (colons in a graph node id,
// `&`/`#`/spaces in a title), not a sanitisation measure. `BlastRadius.tsx`'s
// existing `?node=` comment records that `useSearchParams` decodes on read,
// so encoding here is the correct half of that contract.
export const NAVIGATION_ROUTE_BUILDERS: Record<
  'document' | 'graph_node',
  (targetId: string, systemId: string) => string
> = {
  document: (targetId, systemId) => {
    const encodedSystemId = encodeURIComponent(systemId)
    const encodedTargetId = encodeURIComponent(targetId)
    return `/knowledge?system=${encodedSystemId}&document=${encodedTargetId}`
  },
  graph_node: (targetId, systemId) => {
    const encodedSystemId = encodeURIComponent(systemId)
    const encodedTargetId = encodeURIComponent(targetId)
    return `/blast-radius?system=${encodedSystemId}&node=${encodedTargetId}`
  },
}

// Mirrors the backend's `_terminal_graph_node` exactly (06.1-02,
// `compute_navigation_target()`'s own helper) -- the two are deliberate
// twins across the API boundary, following the project's existing "two type
// representations, converted explicitly at the boundary" convention rather
// than shipping the computed path from the server.
export function terminalGraphNode(graphPath: string[] | null | undefined): string | null {
  if (graphPath === null || graphPath === undefined || graphPath.length === 0) {
    return null
  }
  return graphPath[graphPath.length - 1]
}

// A `kind` the client does not recognise is a destination the client does
// not go to -- returns `null` rather than throwing, so an unrecognised
// backend value degrades to "no navigation" instead of a crash.
export function navigationHref(target: NavigationTarget): string | null {
  const builder = NAVIGATION_ROUTE_BUILDERS[target.kind]
  if (builder === undefined) {
    return null
  }
  return builder(target.target_id, target.system_id)
}

// `systemId` is the one the page sent with the request -- never read from
// the evidence item itself, since `RetrievalEvidenceItem` carries no system
// field and inferring one would be exactly the client-invented fallback
// EvidenceView.tsx's own module comment forbids.
export function evidenceHref(item: RetrievalEvidenceItem, systemId: string): string | null {
  if (item.evidence_type === 'document' && item.document_id) {
    return NAVIGATION_ROUTE_BUILDERS.document(item.document_id, systemId)
  }
  if (item.evidence_type === 'graph_relationship') {
    const node = terminalGraphNode(item.graph_path)
    if (node !== null) {
      return NAVIGATION_ROUTE_BUILDERS.graph_node(node, systemId)
    }
  }
  return null
}

export function evidenceLinkLabel(item: RetrievalEvidenceItem): string | null {
  if (item.evidence_type === 'document' && item.document_id) {
    return 'Open in Knowledge'
  }
  if (item.evidence_type === 'graph_relationship' && terminalGraphNode(item.graph_path) !== null) {
    return 'Open in Blast Radius'
  }
  return null
}
