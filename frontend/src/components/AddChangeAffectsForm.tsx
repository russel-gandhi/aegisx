import { useState } from 'react'
import {
  createChangeAffects,
  ApiError,
  CHANGE_AFFECTS_ENTITY_TYPES,
} from '../lib/api'

/**
 * "Fill the gap" feature: `change_affects` (backing the evidence graph's
 * `CHANGE --AFFECTS--> X` edge) previously had no write path -- only a
 * static seed fixture for one demo change. Rendered by `BlastRadius.tsx`
 * only when the selected node is a CHANGE node and the current identity
 * is "IT System Manager" (server-side RBAC in `app/routes/changes.py` is
 * the real gate; this component's own visibility is a convenience, not a
 * security control, matching every other role-gated affordance in this
 * codebase).
 *
 * Explicit-rebuild-only reminder: a successful submit does NOT refresh
 * this page's graph -- the new edge is real in Postgres immediately, but
 * `graph_nodes`/`graph_edges` (what this page actually reads) stays
 * stale until an operator calls the evidence-graph rebuild endpoint, per
 * this codebase's D-01/D-02 design. The success message says so
 * explicitly rather than implying the graph on screen just updated.
 */

interface AddChangeAffectsFormProps {
  changeId: string
}

export default function AddChangeAffectsForm({ changeId }: AddChangeAffectsFormProps) {
  const [entityType, setEntityType] = useState<string>(CHANGE_AFFECTS_ENTITY_TYPES[0])
  const [entityId, setEntityId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (entityId.trim().length === 0 || submitting) return
    setSubmitting(true)
    setError(null)
    setSuccess(false)
    try {
      await createChangeAffects(changeId, { entity_type: entityType, entity_id: entityId.trim() })
      setSuccess(true)
      setEntityId('')
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to record change impact')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card p-4">
      <h3 className="text-[13px] font-semibold text-ink">Add Affected Entity</h3>
      <p className="mt-1 text-xs text-ink-faint">
        Record that {changeId} affects another requirement, test case, document, design
        element, or risk.
      </p>
      <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2">
        <select
          className="input-field"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
        >
          {CHANGE_AFFECTS_ENTITY_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <input
          className="input-field"
          placeholder="Entity id, e.g. URS-042"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
        />
        <button type="submit" className="btn btn-secondary" disabled={submitting}>
          {submitting ? 'Recording…' : 'Add'}
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red">{error}</p>}
      {success && (
        <p className="mt-2 text-xs text-mint">
          Recorded. This edge won't appear on the graph above until the evidence graph is
          rebuilt (POST /api/systems/{'{system_id}'}/evidence-graph/rebuild).
        </p>
      )}
    </div>
  )
}
