/**
 * Shared "list of known systems" hook, backed by the real `GET /api/systems`
 * endpoint (`backend/app/routes/systems.py`) instead of any page's own
 * hardcoded `SYSTEM_IDS` array. Added alongside the "add a new system"
 * feature (`POST /api/systems`) so a newly created system becomes visible
 * to any consumer of this hook without a rebuild.
 *
 * Deliberately minimal: no caching layer, no global store -- each mounted
 * consumer fetches independently, matching this codebase's existing
 * per-page `useEffect` + `useState` data-fetching convention (see
 * `AuditReadiness.tsx`, `Suppliers.tsx`).
 */

import { useEffect, useState } from 'react'
import { fetchSystems, type SystemRecord } from './api'

export interface UseSystemsResult {
  systems: SystemRecord[]
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useSystems(): UseSystemsResult {
  const [systems, setSystems] = useState<SystemRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refetchToken, setRefetchToken] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSystems()
      .then((result) => {
        if (!cancelled) setSystems(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load systems')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refetchToken])

  return {
    systems,
    loading,
    error,
    refetch: () => setRefetchToken((token) => token + 1),
  }
}
