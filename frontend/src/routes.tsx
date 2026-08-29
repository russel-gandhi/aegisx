import type { ComponentType } from 'react'
import CommandCentre from './pages/CommandCentre'
import Copilot from './pages/Copilot'
import FindingInvestigation from './pages/FindingInvestigation'
import AuditReadiness from './pages/AuditReadiness'
import BlastRadius from './pages/BlastRadius'
import Suppliers from './pages/Suppliers'
import Actions from './pages/Actions'
import AssuranceLab from './pages/AssuranceLab'
import TrustCentre from './pages/TrustCentre'
import InspectionSimulator from './pages/InspectionSimulator'
import Knowledge from './pages/Knowledge'

export interface RouteDefinition {
  path: string
  label: string
  Component: ComponentType
}

// Bible Section 11 numbering skips 11.4 entirely (11.3 Audit Readiness is immediately
// followed by 11.5 Supplier Intelligence) — that is why this table has eight entries, not
// seven, and why the gap between AuditReadiness and Suppliers below is deliberate, not a
// missing page. 11.4 is almost certainly the Blast Radius page, which gets its own ticket
// (SENT-3-04) in Phase 4 — that phase appends a ninth `/blast-radius` entry to this array;
// adding it requires no structural change to the table or the router that consumes it.
export const routes: RouteDefinition[] = [
  { path: '/', label: 'Command Centre', Component: CommandCentre }, // 11.1
  { path: '/copilot', label: 'Ask GxP Copilot', Component: Copilot }, // 11.2
  // Phase 4 (EVID-03, D-04): a deliberate, user-approved addition beyond
  // Bible Section 11's nine pages, placed immediately after /copilot so
  // this investigation experience sits next to the Copilot page it will
  // later be embedded in. The full Copilot chat that would eventually
  // host this card does not land until Phase 6. Routed to SENT-7-05 for
  // Bible reconciliation.
  { path: '/findings', label: 'Evidence Investigation', Component: FindingInvestigation },
  { path: '/audit-readiness', label: 'Audit Readiness', Component: AuditReadiness }, // 11.3
  { path: '/blast-radius', label: 'Blast Radius', Component: BlastRadius }, // 11.4
  // Phase 06.1 (plan 06.1-05, RAG-01, D-10/D-12): a deliberate, one new
  // flat top-level route -- not a re-grouping of the table above. UI_SPEC.md
  // §5's six-item grouped information architecture is a separate, larger
  // piece of work this phase does not attempt; collapsing the existing
  // flat routes into that structure is explicitly out of scope here.
  { path: '/knowledge', label: 'Knowledge', Component: Knowledge },
  { path: '/suppliers', label: 'Supplier Intelligence', Component: Suppliers }, // 11.5
  { path: '/actions', label: 'Actions', Component: Actions }, // 11.6
  { path: '/assurance-lab', label: 'Assurance Lab', Component: AssuranceLab }, // 11.7
  { path: '/trust-centre', label: 'Trust Centre', Component: TrustCentre }, // 11.8
  { path: '/inspection-simulator', label: 'Inspection Simulator', Component: InspectionSimulator }, // 11.9
]
