// dataviz skill mark specs: thin marks, 4px rounded data-ends anchored to
// the baseline, 2px surface gap between adjacent fills. Used only where a
// real denominator exists (HealthMiniCard's "N open / M checks" cards) --
// never fabricated for a raw overdue-count card with no known total
// (CommandCentre's Access Reviews / Supplier cards deliberately have no
// Meter, since there is no total-reviews/total-suppliers figure this page
// actually has).
export interface MeterSegment {
  value: number
  className: string // a background-color utility, e.g. "bg-mint"
  label: string // for the accessible sr-only breakdown, never shown visually per segment
}

export interface MeterProps {
  segments: MeterSegment[]
  total: number
}

export default function Meter({ segments, total }: MeterProps) {
  if (total <= 0) return null
  return (
    <div className="mt-2 flex h-1.5 w-full gap-0.5 overflow-hidden rounded-full bg-white/[0.06]">
      {segments
        .filter((s) => s.value > 0)
        .map((s, i) => (
          <div
            key={i}
            role="presentation"
            className={`h-full rounded-full ${s.className}`}
            style={{ width: `${(s.value / total) * 100}%` }}
            title={`${s.label}: ${s.value}`}
          />
        ))}
    </div>
  )
}
