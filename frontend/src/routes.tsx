import type { ComponentType } from 'react'
import CommandCentre from './pages/CommandCentre'
import Copilot from './pages/Copilot'
import AuditReadiness from './pages/AuditReadiness'
import BlastRadius from './pages/BlastRadius'
import Suppliers from './pages/Suppliers'
import Actions from './pages/Actions'
import AssuranceLab from './pages/AssuranceLab'
import TrustCentre from './pages/TrustCentre'
import InspectionSimulator from './pages/InspectionSimulator'

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
  { path: '/audit-readiness', label: 'Audit Readiness', Component: AuditReadiness }, // 11.3
  { path: '/blast-radius', label: 'Blast Radius', Component: BlastRadius }, // 11.4
  { path: '/suppliers', label: 'Supplier Intelligence', Component: Suppliers }, // 11.5
  { path: '/actions', label: 'Actions', Component: Actions }, // 11.6
  { path: '/assurance-lab', label: 'Assurance Lab', Component: AssuranceLab }, // 11.7
  { path: '/trust-centre', label: 'Trust Centre', Component: TrustCentre }, // 11.8
  { path: '/inspection-simulator', label: 'Inspection Simulator', Component: InspectionSimulator }, // 11.9
]
