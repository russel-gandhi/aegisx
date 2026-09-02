// Shimmering placeholder block (motion-ui skill's "Skeleton loading"
// pattern), replacing plain "Loading…" text across CommandCentre,
// Knowledge, and AuditReadiness. Pure CSS animation (`.skeleton-shimmer`,
// index.css) rather than a motion.div loop -- a skeleton is inherently
// decorative/ambient (not state-communicating beyond "this is loading",
// which its presence alone already says), so there is no reason to pay a
// JS animation's cost for it. `prefers-reduced-motion` is already handled
// globally (index.css's existing `animation-duration: 0.001ms` rule) --
// this component needs no motion.ts import of its own.
export interface SkeletonProps {
  className?: string
  // Repeats this many skeleton rows stacked with a small gap -- the common
  // case (a list of unknown-but-plausible length) without every caller
  // re-deriving its own .map().
  rows?: number
}

export default function Skeleton({ className = 'h-4 w-full', rows = 1 }: SkeletonProps) {
  if (rows === 1) {
    return <div aria-hidden="true" className={`skeleton-shimmer rounded-md ${className}`} />
  }
  return (
    <div aria-hidden="true" className="space-y-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={`skeleton-shimmer rounded-md ${className}`} />
      ))}
    </div>
  )
}
