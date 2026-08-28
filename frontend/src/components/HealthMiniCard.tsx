import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'

// Phase 6 (06-02, Task 2, D-07): shared shell for the Command Centre's 6
// fixed mini-cards. Each card's `status` is independent of the other 5 --
// a card renders its own "Loading…"/error state driven solely by its own
// backing call(s), per 06-UI-SPEC.md's per-card loading/error rows.
export interface HealthMiniCardProps {
  title: string
  status: 'loading' | 'ready' | 'error'
  children?: ReactNode
  errorText?: string
  style?: CSSProperties
}

const DEFAULT_ERROR_TEXT = "Couldn't load this signal."

// 06-UI-SPEC.md Animation Contract: "Subtle fade-in + 4px slide-up ...
// staggered ~40ms per card via inline style={{ transitionDelay }}". The
// mount transition itself (opacity-0/translate-y-1 -> opacity-100/
// translate-y-0) is local to this component; the caller only supplies the
// per-card `transitionDelay` via `style`.
function useMountTransition(): boolean {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  return mounted
}

export default function HealthMiniCard({
  title,
  status,
  children,
  errorText,
  style,
}: HealthMiniCardProps) {
  const mounted = useMountTransition()

  return (
    <div
      data-testid="health-mini-card"
      data-status={status}
      style={style}
      className={`rounded-lg border border-slate-800 bg-slate-900 p-4 transition-all duration-300 ease-out ${
        mounted ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
      }`}
    >
      <p className="text-lg font-semibold text-slate-100">{title}</p>
      <div className="mt-2 text-sm">
        {status === 'loading' && <p className="text-slate-400">Loading…</p>}
        {status === 'error' && <p className="text-red-400">{errorText ?? DEFAULT_ERROR_TEXT}</p>}
        {status === 'ready' && children}
      </div>
    </div>
  )
}
