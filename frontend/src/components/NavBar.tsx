import { NavLink } from 'react-router-dom'
import {
  LayoutGrid,
  MessageSquareText,
  SearchCheck,
  ClipboardCheck,
  Share2,
  BookOpenText,
  Truck,
  ListChecks,
  ShieldCheck,
  Fingerprint,
  Timer,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { routes } from '../routes'

// One icon per route path, purely presentational -- routes.tsx stays the
// single source of truth for the route table itself (path/label/Component);
// this map only adds a visual affordance next to labels that already exist.
const ROUTE_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  '/': LayoutGrid,
  '/copilot': MessageSquareText,
  '/findings': SearchCheck,
  '/audit-readiness': ClipboardCheck,
  '/blast-radius': Share2,
  '/knowledge': BookOpenText,
  '/suppliers': Truck,
  '/actions': ListChecks,
  '/assurance-lab': ShieldCheck,
  '/trust-centre': Fingerprint,
  '/inspection-simulator': Timer,
}

export default function NavBar() {
  return (
    <header className="glass sticky top-0 z-20 border-b border-white/[0.07]">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-2.5 sm:px-6">
        <div className="flex shrink-0 items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-[10px] bg-gradient-to-br from-[#3d97ff] to-[#0a56e8] text-[11px] font-extrabold text-white shadow-[0_6px_18px_rgba(47,139,255,0.4)]">
            AX
          </div>
          <div className="hidden leading-tight sm:block">
            <div className="text-[13px] font-semibold tracking-tight text-ink">AegisX AI</div>
            <div className="text-[9px] font-medium uppercase tracking-[0.14em] text-ink-faint">
              Audit-Ready Copilot
            </div>
          </div>
        </div>

        <nav
          className="scrollbar-none flex min-w-0 flex-1 items-center gap-1 overflow-x-auto"
          aria-label="Primary"
        >
          {routes.map((route) => {
            const Icon = ROUTE_ICONS[route.path]
            return (
              <NavLink
                key={route.path}
                to={route.path}
                end={route.path === '/'}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium whitespace-nowrap transition-all ${
                    isActive
                      ? 'bg-accent-soft text-ink shadow-[0_0_0_1px_rgba(47,139,255,0.35)_inset]'
                      : 'text-ink-muted hover:bg-white/[0.06] hover:text-ink'
                  }`
                }
              >
                {Icon ? <Icon className="h-3.5 w-3.5 shrink-0" /> : null}
                {route.label}
              </NavLink>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
