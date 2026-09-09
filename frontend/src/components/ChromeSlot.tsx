import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * Portals a page's own control into the persistent app chrome -- currently
 * the right-hand end of the role bar (`RoleSelector`), which sits directly
 * beneath the nav bar.
 *
 * Why a portal rather than lifting selection into a shared store: the four
 * pages that own a system picker do NOT agree on what one is. Command
 * Centre's includes a synthetic "All Systems" scope; Knowledge's includes
 * an empty "all documents" option and syncs `?system=`; Blast Radius syncs
 * `?system=` too but validates against its own option list and rejects a
 * node id from another system's graph; Finding Investigation has neither.
 * Collapsing four different option sets and two different URL contracts
 * into one global value would change behaviour on every one of those pages.
 * A portal moves only where the control is PAINTED -- each page keeps its
 * own state, its own options, and its own URL syncing, unchanged.
 *
 * Falls back to rendering `children` in place when no host exists, rather
 * than rendering nothing. Two cases need this, and both are real:
 *
 *  1. The first commit. `host` is resolved in an effect, which runs after
 *     the initial render, so there is always one paint with no host.
 *  2. A page mounted outside the app chrome. The test suite renders pages
 *     directly into a `MemoryRouter` with no `AppShell` above them (see
 *     `__tests__/Knowledge.test.tsx`), so `RoleSelector` -- and therefore
 *     the slot -- is absent entirely.
 *
 * Rendering nothing in either case would silently swallow the control: the
 * page would lose its system picker, and the Knowledge tests would fail
 * looking for `knowledge-system-select`. Rendering in place is the honest
 * degradation -- the control is always present, and only its POSITION
 * depends on whether the chrome is there to receive it.
 */

export const CHROME_SLOT_ID = 'app-chrome-right-slot'

export default function ChromeSlot({ children }: { children: ReactNode }) {
  const [host, setHost] = useState<HTMLElement | null>(null)

  useEffect(() => {
    setHost(document.getElementById(CHROME_SLOT_ID))
  }, [])

  if (host === null) return <>{children}</>
  return createPortal(children, host)
}
