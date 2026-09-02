import { useEffect, useRef, useState } from 'react'

// Phase 6 (06-02, Task 2, D-06): the Command Centre readiness dial.
// Hand-rolled SVG arc, per 06-RESEARCH.md's Standard Stack recommendation
// and 06-UI-SPEC.md's "no chart library" decision -- no new runtime
// dependency. Pure presentation: `passed`/`total` are computed by the
// caller from live `assurance-cards` responses (never `gxp_systems.
// readiness_score`, 06-RESEARCH.md Pitfall 1); this component performs no
// fetch of its own.
export interface ReadinessDialProps {
  passed: number
  total: number
}

const SIZE = 188
const STROKE_WIDTH = 13
const RADIUS = (SIZE - STROKE_WIDTH) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const TRACK_COLOR = 'rgba(255,255,255,0.08)'

// 06-UI-SPEC.md Color table, transcribed verbatim: >=80% emerald/mint,
// 50-79% amber, <50% orange (deliberately not red -- red stays reserved
// for destructive/error only). Hex values updated to the 2026-09-02 UI
// overhaul's token palette; the threshold semantics themselves (the
// actual Bible-sourced rule) are unchanged.
function colorForPercent(percent: number): string {
  if (percent >= 80) return '#2fd889' // --color-mint
  if (percent >= 50) return '#ffb020' // --color-amber
  return '#ff8a3d' // orange -- deliberately distinct from --color-red
}

export default function ReadinessDial({ passed, total }: ReadinessDialProps) {
  const percent = total > 0 ? Math.round((passed / total) * 100) : 0
  const [offset, setOffset] = useState(CIRCUMFERENCE)
  const prevPercentRef = useRef<number | null>(null)

  // 06-UI-SPEC.md Animation Contract: "Only animates on data change, not on
  // every re-render (guard with the previous value in state)." The
  // `stroke-dashoffset` CSS transition (below) plays whenever this state
  // update actually changes `offset` -- which only happens when `percent`
  // itself changed since the last commit.
  useEffect(() => {
    if (prevPercentRef.current === percent) {
      return
    }
    prevPercentRef.current = percent
    setOffset(CIRCUMFERENCE * (1 - percent / 100))
  }, [percent])

  const color = colorForPercent(percent)

  return (
    <div
      data-testid="readiness-dial"
      data-percent={percent}
      style={{ width: SIZE, height: SIZE }}
      className="relative"
    >
      <div
        className="absolute inset-6 rounded-full blur-2xl transition-colors duration-500"
        style={{ backgroundColor: color, opacity: 0.16 }}
        aria-hidden="true"
      />
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="relative">
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={TRACK_COLOR}
          strokeWidth={STROKE_WIDTH}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(.2,.8,.2,1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-bold tracking-tight text-ink">{percent}%</span>
        <span className="mt-1 text-[10px] font-semibold tracking-[0.14em] text-ink-faint uppercase">
          Ready
        </span>
      </div>
    </div>
  )
}
