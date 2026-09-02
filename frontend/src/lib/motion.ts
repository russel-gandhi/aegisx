// Shared motion tokens (motion-ui skill, v4.2). Single source of truth for
// every animation's duration/easing/distance in this app -- previously
// each component that animated at all (HealthMiniCard, ChatMessage,
// AutoNavigateNotice) picked its own ad-hoc `duration-200`/`duration-300`
// Tailwind class independently, with no shared vocabulary.
export const motionTokens = {
  duration: {
    fast: 0.18,
    normal: 0.35,
    slow: 0.6,
  },
  easing: {
    smooth: [0.22, 1, 0.36, 1] as [number, number, number, number],
    sharp: [0.4, 0, 0.2, 1] as [number, number, number, number],
  },
  distance: {
    sm: 8,
    md: 16,
    lg: 24,
  },
} as const

// AnimatePresence always needs an explicit `mode` (motion-ui anti-pattern:
// the default "sync" overlaps enter/exit) -- named here so every call site
// picks intentionally rather than typing the string literal.
export const PRESENCE_MODE = {
  waitThenEnter: 'wait',
  popOutInPlace: 'popLayout',
} as const
