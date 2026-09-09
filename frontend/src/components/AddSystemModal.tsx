import { useState } from 'react'
import { X } from 'lucide-react'
import { createSystem, ApiError } from '../lib/api'

/**
 * "Add a new system" feature -- calls `POST /api/systems`
 * (`backend/app/routes/systems.py`), which is gated server-side to the
 * "IT System Manager" role (fail-closed on the server independent of this
 * form ever rendering). `CommandCentre.tsx` only mounts this component
 * for that role already, but this modal makes no assumption about that --
 * a 403 from the server is surfaced as a plain error message like any
 * other failure, never silently retried as a different role.
 */

interface AddSystemModalProps {
  onClose: () => void
  onCreated: (systemId: string) => void
}

const LIFECYCLE_STATES = ['OPERATIONAL', 'IMPLEMENTATION', 'RETIRED'] as const

export default function AddSystemModal({ onClose, onCreated }: AddSystemModalProps) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemOwner, setSystemOwner] = useState('')
  const [lifecycleState, setLifecycleState] = useState<string>(LIFECYCLE_STATES[0])
  const [gxpImpact, setGxpImpact] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = id.trim().length > 0 && name.trim().length > 0 && systemOwner.trim().length > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const created = await createSystem({
        id: id.trim(),
        name: name.trim(),
        description: description.trim().length > 0 ? description.trim() : null,
        system_owner: systemOwner.trim(),
        lifecycle_state: lifecycleState,
        gxp_impact: gxpImpact,
      })
      onCreated(created.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to create system')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Add new system"
      onClick={onClose}
    >
      <div
        className="card-hero w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold tracking-tight text-ink">Add New System</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-ink-muted hover:text-ink"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-muted">
            System ID
            <input
              className="input-field"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="e.g. GXP-LAB-DEMO-03"
              maxLength={50}
              required
            />
          </label>

          <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-muted">
            Name
            <input
              className="input-field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. NovaSynth LIMS"
              maxLength={255}
              required
            />
          </label>

          <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-muted">
            Description
            <textarea
              className="input-field"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </label>

          <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-muted">
            System Owner
            <input
              className="input-field"
              value={systemOwner}
              onChange={(e) => setSystemOwner(e.target.value)}
              placeholder="e.g. Jane Doe"
              maxLength={100}
              required
            />
          </label>

          <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-muted">
            Lifecycle State
            <select
              className="input-field"
              value={lifecycleState}
              onChange={(e) => setLifecycleState(e.target.value)}
            >
              {LIFECYCLE_STATES.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-[13px] font-medium text-ink-muted">
            <input
              type="checkbox"
              checked={gxpImpact}
              onChange={(e) => setGxpImpact(e.target.checked)}
            />
            GxP-impacting system
          </label>

          {error && <p className="text-[13px] text-red">{error}</p>}

          <div className="mt-2 flex items-center justify-end gap-2">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!canSubmit || submitting}>
              {submitting ? 'Creating…' : 'Create System'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
