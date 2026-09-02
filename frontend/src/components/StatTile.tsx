import type { ComponentType } from 'react'
import FadeIn from './FadeIn'

// dataviz skill: "a stat tile or hero number" is the right form when the
// data's job is a single headline, not a comparison -- CommandCentre's
// four top-line KPIs (systems in scope, open findings, pending approvals,
// audit trail status) are exactly that, so this is deliberately NOT a
// chart. Status colors (mint/amber/orange/red) are reserved for state and
// always ship with an icon + label, never color alone (dataviz
// non-negotiables) -- `tone` drives both the icon color and the number
// color together, consistently, never text-color-as-decoration.
export type StatTileTone = 'neutral' | 'good' | 'warning' | 'critical'

const TONE_TEXT: Record<StatTileTone, string> = {
  neutral: 'text-ink',
  good: 'text-mint',
  warning: 'text-amber',
  critical: 'text-red',
}

const TONE_ICON_WRAP: Record<StatTileTone, string> = {
  neutral: 'bg-white/[0.06] text-ink-muted',
  good: 'bg-mint-soft text-mint',
  warning: 'bg-amber-soft text-amber',
  critical: 'bg-red-soft text-red',
}

export interface StatTileProps {
  icon: ComponentType<{ className?: string }>
  label: string
  value: string | number
  tone?: StatTileTone
  delay?: number
}

export default function StatTile({ icon: Icon, label, value, tone = 'neutral', delay = 0 }: StatTileProps) {
  return (
    <FadeIn
      delay={delay}
      className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3"
    >
      <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${TONE_ICON_WRAP[tone]}`}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div className="min-w-0">
        <p className={`text-xl leading-none font-bold tracking-tight ${TONE_TEXT[tone]}`}>{value}</p>
        <p className="mt-1 truncate text-[11px] font-medium tracking-wide text-ink-faint uppercase">
          {label}
        </p>
      </div>
    </FadeIn>
  )
}
