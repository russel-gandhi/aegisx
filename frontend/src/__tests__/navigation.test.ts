import { describe, it, expect } from 'vitest'
import {
  DESTINATION_LABELS,
  NAVIGATION_ROUTE_BUILDERS,
  terminalGraphNode,
  navigationHref,
  evidenceHref,
  evidenceLinkLabel,
} from '../lib/navigation'
import type { NavigationTarget, RetrievalEvidenceItem } from '../lib/api'

function fixtureTarget(overrides: Partial<NavigationTarget> = {}): NavigationTarget {
  return {
    kind: 'document',
    target_id: 'DOC-A',
    label: 'Fixture Validation Protocol',
    system_id: 'GXP-MFG-DEMO-01',
    reason: 'single unambiguous document citation',
    ...overrides,
  }
}

function fixtureEvidenceItem(overrides: Partial<RetrievalEvidenceItem> = {}): RetrievalEvidenceItem {
  return {
    evidence_id: 'EVID-001',
    document_id: 'DOC-A',
    chunk_id: 'CHUNK-001',
    document_title: 'Fixture Validation Protocol',
    section: '3.2 Traceability',
    page: 5,
    content: 'Fixture chunk content.',
    retrieval_method: 'hybrid',
    dense_score: 0.71,
    bm25_score: 4.02,
    reranker_score: 0.88,
    parent_section: '3. Validation',
    graph_path: [],
    regulatory_citations: ['ANNEX11-S4-DOC-001'],
    evidence_type: 'document',
    why_selected: 'Matches the traceability requirement directly.',
    ...overrides,
  }
}

describe('DESTINATION_LABELS', () => {
  it('names the two destination pages', () => {
    expect(DESTINATION_LABELS.document).toBe('Knowledge')
    expect(DESTINATION_LABELS.graph_node).toBe('Blast Radius')
  })
})

describe('terminalGraphNode', () => {
  it('returns the last element of a non-empty graph path', () => {
    expect(terminalGraphNode(['DOCUMENT:DOC-A', 'CHANGE:CHANGE-2026-09'])).toBe(
      'CHANGE:CHANGE-2026-09',
    )
  })

  it('returns null for an empty array', () => {
    expect(terminalGraphNode([])).toBeNull()
  })

  it('returns null for null/undefined', () => {
    expect(terminalGraphNode(null)).toBeNull()
    expect(terminalGraphNode(undefined)).toBeNull()
  })
})

describe('navigationHref', () => {
  it('builds a Knowledge path for a document target', () => {
    const href = navigationHref(
      fixtureTarget({ kind: 'document', target_id: 'DOC-A', system_id: 'GXP-MFG-DEMO-01' }),
    )
    expect(href).toBe('/knowledge?system=GXP-MFG-DEMO-01&document=DOC-A')
  })

  it('builds a Blast Radius path for a graph_node target, URL-encoding the colon', () => {
    const href = navigationHref(
      fixtureTarget({
        kind: 'graph_node',
        target_id: 'CHANGE:CHANGE-2026-09',
        system_id: 'GXP-MFG-DEMO-01',
      }),
    )
    expect(href).toBe('/blast-radius?system=GXP-MFG-DEMO-01&node=CHANGE%3ACHANGE-2026-09')
  })

  it('returns null and throws nothing for an unrecognised kind', () => {
    const target = fixtureTarget({ kind: 'unknown_kind' as unknown as NavigationTarget['kind'] })
    expect(() => navigationHref(target)).not.toThrow()
    expect(navigationHref(target)).toBeNull()
  })
})

describe('evidenceHref / evidenceLinkLabel -- document evidence', () => {
  it('returns the Knowledge path and "Open in Knowledge" label for a document item', () => {
    const item = fixtureEvidenceItem({ evidence_type: 'document', document_id: 'DOC-A' })
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBe(
      '/knowledge?system=GXP-MFG-DEMO-01&document=DOC-A',
    )
    expect(evidenceLinkLabel(item)).toBe('Open in Knowledge')
  })

  it('returns null for a document item with a null document_id', () => {
    const item = fixtureEvidenceItem({
      evidence_type: 'document',
      document_id: null as unknown as string,
    })
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBeNull()
    expect(evidenceLinkLabel(item)).toBeNull()
  })

  it('returns null for a document item with an empty document_id', () => {
    const item = fixtureEvidenceItem({ evidence_type: 'document', document_id: '' })
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBeNull()
    expect(evidenceLinkLabel(item)).toBeNull()
  })
})

describe('evidenceHref / evidenceLinkLabel -- graph relationship evidence', () => {
  it('returns the Blast Radius path for the terminal graph node and "Open in Blast Radius" label', () => {
    const item = fixtureEvidenceItem({
      evidence_type: 'graph_relationship',
      graph_path: ['DOCUMENT:DOC-A', 'RISK:RISK-7'],
    })
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBe(
      '/blast-radius?system=GXP-MFG-DEMO-01&node=RISK%3ARISK-7',
    )
    expect(evidenceLinkLabel(item)).toBe('Open in Blast Radius')
  })

  it('returns null for a graph item with an empty graph_path', () => {
    const item = fixtureEvidenceItem({ evidence_type: 'graph_relationship', graph_path: [] })
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBeNull()
    expect(evidenceLinkLabel(item)).toBeNull()
  })
})

describe('evidenceHref / evidenceLinkLabel -- unrecognised evidence_type', () => {
  it('returns null for both, without throwing', () => {
    const item = fixtureEvidenceItem({ evidence_type: 'model_interpretation' })
    expect(() => evidenceHref(item, 'GXP-MFG-DEMO-01')).not.toThrow()
    expect(evidenceHref(item, 'GXP-MFG-DEMO-01')).toBeNull()
    expect(evidenceLinkLabel(item)).toBeNull()
  })
})

describe('URL-encoding backstop', () => {
  it('round-trips a systemId/target_id containing &, #, a space, and a colon through URLSearchParams unchanged', () => {
    const trickySystemId = 'SYS & Weird#1 name'
    const trickyTargetId = 'DOC:with a & # in it'
    const href = navigationHref(
      fixtureTarget({ kind: 'document', target_id: trickyTargetId, system_id: trickySystemId }),
    )
    expect(href).not.toBeNull()
    const url = new URL(href as string, 'http://x')
    const params = new URLSearchParams(url.search)
    expect(params.get('system')).toBe(trickySystemId)
    expect(params.get('document')).toBe(trickyTargetId)
  })
})

// Exercises both route builders directly, matching the plan's acceptance
// criteria requiring at least 4 encodeURIComponent call sites (2 args x 2
// builders).
describe('NAVIGATION_ROUTE_BUILDERS', () => {
  it('encodes both arguments for the document builder', () => {
    expect(NAVIGATION_ROUTE_BUILDERS.document('DOC A', 'SYS A')).toBe(
      '/knowledge?system=SYS%20A&document=DOC%20A',
    )
  })

  it('encodes both arguments for the graph_node builder', () => {
    expect(NAVIGATION_ROUTE_BUILDERS.graph_node('NODE:A', 'SYS A')).toBe(
      '/blast-radius?system=SYS%20A&node=NODE%3AA',
    )
  })
})
