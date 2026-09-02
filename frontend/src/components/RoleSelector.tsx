import { DEMO_IDENTITIES, setIdentity, useIdentity } from '../lib/identity'

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
      <div className="mx-auto flex max-w-[1400px] items-center gap-2">
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
      </div>
    </div>
  )
}
