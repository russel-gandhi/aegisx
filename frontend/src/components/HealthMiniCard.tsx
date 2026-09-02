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
      className={`group rounded-xl border border-white/[0.08] bg-white/[0.03] p-5 shadow-panel transition-all duration-300 ease-out hover:border-white/[0.14] hover:bg-white/[0.045] ${
        mounted ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
      }`}
    >
      <p className="text-[13px] font-semibold tracking-tight text-ink">{title}</p>
      <div className="mt-3 text-sm">
        {status === 'loading' && (
          <div className="flex items-center gap-2 text-ink-faint">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
            Loading…
          </div>
        )}
        {status === 'error' && (
          <p className="text-red">{errorText ?? DEFAULT_ERROR_TEXT}</p>
        )}
        {status === 'ready' && children}
      </div>
    </div>
  )
}
