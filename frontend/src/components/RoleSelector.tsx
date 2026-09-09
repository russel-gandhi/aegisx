import { DEMO_IDENTITIES, setIdentity, useIdentity } from '../lib/identity'
import { CHROME_SLOT_ID } from './ChromeSlot'

// Persistent app-chrome control (05-UI-SPEC.md "Interaction Notes"): the
// operator picks one of the three Bible-defined roles before ever reaching
// a write-capable action ("Generate CAPA" on /findings, Approve/Reject on
// /actions). Selecting a role is client state only -- no server round
// trip -- see `lib/identity.ts`'s own docstring for why this is never a
// security control.
//
// Per 05-UI-SPEC.md's Color section, the reserved emerald/mint accent is
// exclusive to the Approve button/APPROVED-EXECUTED badges/live-indicator
// dot and must not appear here -- the selected state uses the neutral
// accent-blue treatment the nav-bar's own active link already uses, so
// this reads as the same control family rather than a competing one.
export default function RoleSelector() {
  const identity = useIdentity()

  return (
    <div
      role="group"
      aria-label="Demo role selector"
      className="border-b border-white/[0.06] bg-black/20 px-4 py-2 sm:px-6"
    >
      {/* `flex-wrap` + `gap-y-2`: the row now carries the role pills AND a
          page's system picker, which together overflow a phone-width
          viewport. Wrapping drops the picker onto its own line there
          instead of letting it run off the right edge. */}
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-2 gap-y-2">
        <span className="hidden text-[10px] font-semibold tracking-[0.1em] text-ink-faint uppercase sm:inline">
          Viewing as
        </span>
        <div className="flex gap-1 rounded-full border border-white/[0.07] bg-white/[0.03] p-1">
          {DEMO_IDENTITIES.map((demoIdentity) => {
            const isSelected = demoIdentity.role === identity.role
            return (
              <button
                key={demoIdentity.role}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setIdentity(demoIdentity)}
                className={`rounded-full px-3 py-1 text-[12px] font-medium transition-all ${
                  isSelected
                    ? 'bg-accent text-white shadow-[0_2px_10px_rgba(47,139,255,0.45)]'
                    : 'text-ink-muted hover:bg-white/[0.06] hover:text-ink'
                }`}
              >
                {demoIdentity.role}
              </button>
            )
          })}
        </div>

        {/* Right-hand chrome slot: pages portal their own system picker in
            here via <ChromeSlot>, so "which system am I looking at" sits in
            persistent chrome at the far right of this bar rather than
            drifting down the page body. `ml-auto` on the slot -- not
            `justify-between` on the row -- keeps the role pills hard left
            beside their "Viewing as" label even when nothing fills the
            slot (a route with no picker at all, e.g. /trust-centre); an
            empty slot then collapses to zero width and changes nothing. */}
        <div id={CHROME_SLOT_ID} className="flex min-w-0 items-center gap-2 sm:ml-auto" />
      </div>
    </div>
  )
}
