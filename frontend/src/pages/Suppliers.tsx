import { useEffect, useState } from 'react'
import { fetchSuppliers, type SupplierRecord } from '../lib/api'

// Bible Section 11.5: "Supplier registry for each system showing all
// vendors, their qualification status, reassessment due dates, and open
// CAPAs. Explicitly highlights the `DataSync Solutions` overdue finding
// injected via the seed script." Every row here comes straight from
// `GET /api/systems/{id}/suppliers` (`backend/app/routes/suppliers.py`) --
// no client-side scoring or fabricated status.
const SYSTEM_IDS = ['GXP-MFG-DEMO-01', 'BUS-IT-DEMO-02'] as const
type SystemId = (typeof SYSTEM_IDS)[number]

type CallStatus = 'loading' | 'ready' | 'error'

function formatDate(ns: number | null): string {
  if (ns === null) return 'Not scheduled'
  return new Date(ns / 1_000_000).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function StatusPill({ status }: { status: string | null }) {
  const label = status ?? 'UNKNOWN'
  const tone =
    label === 'APPROVED'
      ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800'
      : label === 'REJECTED' || label === 'SUSPENDED'
        ? 'bg-red-950/50 text-red-400 border-red-800'
        : 'bg-slate-800 text-slate-300 border-slate-700'
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      {label}
    </span>
  )
}

export default function Suppliers() {
  const [systemId, setSystemId] = useState<SystemId>('GXP-MFG-DEMO-01')
  const [status, setStatus] = useState<CallStatus>('loading')
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([])

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    fetchSuppliers(systemId)
      .then((res) => {
        if (cancelled) return
        setSuppliers(res.suppliers)
        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [systemId])

  const overdueCount = suppliers.filter((s) => s.is_overdue).length

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Supplier Intelligence</h1>
      <p className="mt-2 max-w-2xl text-slate-400">
        Every vendor registered against this system, their qualification status, and when their
        next reassessment is due &mdash; read directly from live database state.
      </p>

      <div className="mt-4 flex items-center gap-3">
        <label htmlFor="suppliers-system" className="text-sm text-slate-400">
          System
        </label>
        <select
          id="suppliers-system"
          className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
          value={systemId}
          onChange={(e) => setSystemId(e.target.value as SystemId)}
        >
          {SYSTEM_IDS.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>

        {status === 'ready' && overdueCount > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-orange-800 bg-orange-950/40 px-3 py-1 text-xs font-medium text-orange-300">
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                clipRule="evenodd"
              />
            </svg>
            {overdueCount} reassessment{overdueCount === 1 ? '' : 's'} overdue
          </span>
        )}
      </div>

      <div className="mt-6 overflow-x-auto rounded-lg border border-slate-800">
        {status === 'loading' && <p className="p-6 text-sm text-slate-400">Loading suppliers&hellip;</p>}
        {status === 'error' && (
          <p className="p-6 text-sm text-red-400">Couldn&rsquo;t load the supplier registry. Refresh to retry.</p>
        )}
        {status === 'ready' && suppliers.length === 0 && (
          <p className="p-6 text-sm text-slate-400">No suppliers registered for this system.</p>
        )}
        {status === 'ready' && suppliers.length > 0 && (
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 font-medium">Supplier</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Reassessment Due</th>
                <th className="px-4 py-3 font-medium">Latest Assessment</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr
                  key={s.supplier_id}
                  data-testid="supplier-row"
                  data-overdue={s.is_overdue}
                  className={`border-b border-slate-800/60 last:border-0 ${
                    s.is_overdue ? 'bg-orange-950/20' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-medium text-slate-100">{s.name}</td>
                  <td className="px-4 py-3">
                    <StatusPill status={s.status} />
                  </td>
                  <td className={`px-4 py-3 ${s.is_overdue ? 'font-medium text-orange-300' : 'text-slate-300'}`}>
                    {formatDate(s.reassessment_due_date_ns)}
                    {s.is_overdue && <span className="ml-2 text-xs text-orange-400">(overdue)</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {s.latest_assessment_result ?? (
                      <span className="text-slate-500">No assessment on record</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
