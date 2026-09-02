import type { ComponentType, CSSProperties, ReactNode } from 'react'
import FadeIn from './FadeIn'
import Skeleton from './Skeleton'

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
  // Optional scannability aid (dataviz skill: "status colors ship with an
  // icon + label, never color alone"). Purely presentational -- absent for
  // any caller that doesn't pass one, same as before this prop existed.
  icon?: ComponentType<{ className?: string }>
  // 2026-09-03 bento redesign: lets a caller widen a specific card (e.g.
  // `lg:col-span-2`) without this component needing to know about grid
  // layout itself -- appended after the base classes so a caller's
  // grid-span utility can't be accidentally overridden by them.
  className?: string
}

const DEFAULT_ERROR_TEXT = "Couldn't load this signal."

export default function HealthMiniCard({
  title,
  status,
  children,
  errorText,
  style,
  icon: Icon,
  className = '',
}: HealthMiniCardProps) {
  // 06-UI-SPEC.md Animation Contract: "Subtle fade-in + 4px slide-up ...
  // staggered ~40ms per card" -- previously a hand-rolled `useMountTransition`
  // hook local to this file (now shared as FadeIn, motion-ui skill item 2).
  // The caller's `style.transitionDelay` (seconds-as-ms, e.g. "40ms")
  // becomes FadeIn's `delay` (seconds) below.
  const rawDelay = style?.transitionDelay
  const delaySeconds =
    typeof rawDelay === 'string' && rawDelay.endsWith('ms')
      ? parseFloat(rawDelay) / 1000
      : 0

  return (
    <FadeIn
      data-testid="health-mini-card"
      data-status={status}
      style={style}
      delay={delaySeconds}
      className={`group rounded-xl border border-white/[0.08] bg-white/[0.03] p-5 shadow-panel transition-colors duration-300 ease-out hover:border-white/[0.14] hover:bg-white/[0.045] ${className}`}
    >
      <div className="flex items-center gap-2">
        {Icon && (
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-white/[0.06] text-ink-muted">
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
        <p className="text-[13px] font-semibold tracking-tight text-ink">{title}</p>
      </div>
      <div className="mt-3 text-sm">
        {status === 'loading' && <Skeleton className="h-4 w-3/4" />}
        {status === 'error' && (
          <p className="text-red">{errorText ?? DEFAULT_ERROR_TEXT}</p>
        )}
        {status === 'ready' && children}
      </div>
    </FadeIn>
  )
}
