import { motion, useReducedMotion, type HTMLMotionProps } from 'motion/react'
import { motionTokens } from '../lib/motion'

// Shared mount-transition primitive (motion-ui skill). Replaces three
// previously-duplicated implementations of the identical "fade in, slide up
// slightly" pattern (HealthMiniCard.tsx's useMountTransition,
// ChatMessage.tsx's and AutoNavigateNotice.tsx's own useFadeIn) with one
// component, so the animation only needs fixing/tuning in one place and a
// future component gets real prefers-reduced-motion support automatically
// (useReducedMotion) instead of relying on the blunt global CSS killswitch
// in index.css.
export interface FadeInProps extends Omit<HTMLMotionProps<'div'>, 'initial' | 'animate' | 'transition'> {
  // Stagger offset in seconds -- e.g. HealthMiniCard's 6 cards each pass a
  // slightly larger delay so they cascade in rather than popping together.
  delay?: number
  // Vertical travel distance in px. Defaults to motionTokens.distance.sm
  // (8px), matching the original 06-UI-SPEC.md "4px slide-up" contract's
  // spirit closely enough while using the shared token scale.
  distance?: number
}

export default function FadeIn({ delay = 0, distance = motionTokens.distance.sm, ...rest }: FadeInProps) {
  const reduce = useReducedMotion()

  return (
    <motion.div
      initial={{ opacity: 0, y: reduce ? 0 : distance }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduce ? motionTokens.duration.fast : motionTokens.duration.normal,
        ease: motionTokens.easing.smooth,
        delay: reduce ? 0 : delay,
      }}
      {...rest}
    />
  )
}
