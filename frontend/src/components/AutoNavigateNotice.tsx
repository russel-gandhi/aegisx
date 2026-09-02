import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { NavigationTarget } from '../lib/api'
import { navigationHref, DESTINATION_LABELS } from '../lib/navigation'

/**
 * D-13's cancellable auto-navigate notice (Phase 06.1, plan 06.1-08,
 * RAG-06).
 *
 * The grounded answer renders first, and this notice second -- a product
 * whose thesis is "never blindly trust AI" cannot move the user off a
 * grounded answer before they have seen it (`ChatMessage.tsx`'s own render
 * order enforces this: this component always sits below `EvidenceView`).
 * The timer is cancellable because an uncancellable one would be a hijack
 * no matter how short (WCAG 2.2.1 Timing Adjustable).
 */

export const AUTO_NAVIGATE_DELAY_MS = 3000
export const STAY_HERE_LABEL = 'Stay here'
// 06.1-UI-SPEC.md Copywriting Contract, transcribed verbatim.
export const CANCELLED_COPY =
  'Staying here. Use the evidence links below to open a source yourself.'

export function autoNavigateCopy(destination: string, label: string): string {
  return `Opening ${destination} for ${label} — all cited evidence points to one source.`
}

export interface AutoNavigateNoticeProps {
  target: NavigationTarget | null
  armed: boolean
  onCancelled: () => void
}

// Reused from ChatMessage.tsx's own technique (06-UI-SPEC.md Animation
// Contract): fade-in only, decorative, never gates readability.
function useFadeIn(): boolean {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    setVisible(true)
  }, [])
  return visible
}

export default function AutoNavigateNotice({ target, armed, onCancelled }: AutoNavigateNoticeProps) {
  const navigate = useNavigate()
  const visible = useFadeIn()
  const [cancelled, setCancelled] = useState(false)

  const href = target !== null ? navigationHref(target) : null

  // Guards arming so the effect can run twice -- which React StrictMode
  // deliberately makes it do in development -- while arming exactly one
  // setTimeout. Separate from `cancelled` (React state, causes a
  // re-render) so that a cancel lands instantly via the ref check inside
  // the timeout callback, even in the same tick the timer would fire.
  const armedOnceRef = useRef(false)
  const cancelledRef = useRef(false)
  const timeoutIdRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!armed || href === null) {
      return
    }
    if (armedOnceRef.current) {
      return
    }
    armedOnceRef.current = true

    timeoutIdRef.current = setTimeout(() => {
      // A cancel that lands in the same tick still wins.
      if (!cancelledRef.current) {
        navigate(href)
      }
    }, AUTO_NAVIGATE_DELAY_MS)

    return () => {
      if (timeoutIdRef.current !== null) {
        clearTimeout(timeoutIdRef.current)
      }
    }
    // armed/href are the only inputs that matter for (re-)arming; navigate
    // is stable from react-router-dom.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [armed, href])

  if (!armed || href === null) {
    return null
  }

  function handleStayHere() {
    cancelledRef.current = true
    if (timeoutIdRef.current !== null) {
      clearTimeout(timeoutIdRef.current)
    }
    setCancelled(true)
    onCancelled()
  }

  const opacityClass = visible ? 'opacity-100' : 'opacity-0'

  if (cancelled) {
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="auto-navigate-notice-cancelled"
        className={`glass rounded-lg px-3 py-2 text-xs text-ink-muted transition-opacity duration-200 ${opacityClass}`}
      >
        {CANCELLED_COPY}
      </div>
    )
  }

  // `target` is non-null here -- `href` (derived from it) is non-null, and
  // the early return above already excluded `href === null`.
  const destination = DESTINATION_LABELS[(target as NavigationTarget).kind]
  const label = (target as NavigationTarget).label

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="auto-navigate-notice"
      className={`glass flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-xs text-ink-muted transition-opacity duration-200 ${opacityClass}`}
    >
      <span>{autoNavigateCopy(destination, label)}</span>
      <button
        type="button"
        data-testid="auto-navigate-stay-here"
        onClick={handleStayHere}
        className="rounded-md border border-white/[0.14] px-2 py-0.5 text-ink hover:bg-white/[0.06]"
      >
        {STAY_HERE_LABEL}
      </button>
    </div>
  )
}
