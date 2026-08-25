import { DEMO_IDENTITIES, setIdentity, useIdentity } from '../lib/identity'

// Persistent app-chrome control (05-UI-SPEC.md "Interaction Notes"): the
// operator picks one of the three Bible-defined roles before ever reaching
// a write-capable action ("Generate CAPA" on /findings, Approve/Reject on
// /actions). Selecting a role is client state only -- no server round
// trip -- see `lib/identity.ts`'s own docstring for why this is never a
// security control.
//
// Styled to match `NavBar.tsx`'s exact pill classes
// (`rounded px-3 py-1.5 text-sm font-medium`) so this reads as the same
// chrome family, not a new control language. Per 05-UI-SPEC.md's Color
// section, the reserved emerald accent is exclusive to the Approve
// button/APPROVED-EXECUTED badges/live-indicator dot and must not appear
// here -- the selected state uses the same neutral `bg-slate-700` the
// nav-bar active link already uses.
export default function RoleSelector() {
  const identity = useIdentity()

  return (
    <div
      role="group"
      aria-label="Demo role selector"
      className="flex flex-wrap gap-1 border-b border-slate-800 bg-slate-900 px-4 py-2"
    >
      {DEMO_IDENTITIES.map((demoIdentity) => {
        const isSelected = demoIdentity.role === identity.role
        return (
          <button
            key={demoIdentity.role}
            type="button"
            aria-pressed={isSelected}
            onClick={() => setIdentity(demoIdentity)}
            className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
              isSelected
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            {demoIdentity.role}
          </button>
        )
      })}
    </div>
  )
}
