import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import BlastRadiusPanel from '../components/BlastRadiusPanel'
import type { BlastRadiusResponse } from '../lib/api'

// Bible Section 14.3's own worked-example shape: four direct dependencies,
// two indirect, no affected controls, HIGH gxp impact.
const IMPACT_RESULT: BlastRadiusResponse = {
  system_id: 'GXP-MFG-DEMO-01',
  source_node_id: 'CHANGE:CR-2026-089',
  direct_dependencies: [
    'REQUIREMENT:URS-042',
    'TEST_CASE:TC-001',
    'RISK:RA-001',
    'SYSTEM:GXP-MFG-DEMO-01',
  ],
  indirect_dependencies: ['REQUIREMENT:URS-043', 'TEST_CASE:TC-002'],
  affected_requirements: ['REQUIREMENT:URS-042', 'REQUIREMENT:URS-043'],
  affected_tests: ['TEST_CASE:TC-001'],
  affected_risks: ['RISK:RA-001'],
  affected_changes: [],
  affected_controls: [],
  affected_systems: ['SYSTEM:GXP-MFG-DEMO-01'],
  potential_gxp_impact: 'HIGH',
  highest_impact_downstream: 'REQUIREMENT:URS-042',
}

const EMPTY_RESULT: BlastRadiusResponse = {
  system_id: 'BUS-IT-DEMO-02',
  source_node_id: 'SYSTEM:BUS-IT-DEMO-02',
  direct_dependencies: [],
  indirect_dependencies: [],
  affected_requirements: [],
  affected_tests: [],
  affected_risks: [],
  affected_changes: [],
  affected_controls: [],
  affected_systems: [],
  potential_gxp_impact: 'NONE',
  highest_impact_downstream: null,
}

describe('BlastRadiusPanel', () => {
  it('renders the four summary lines with their labels and the correct counts/grade', () => {
    render(<BlastRadiusPanel result={IMPACT_RESULT} loading={false} error={null} />)
    // Anchored exact matches -- "direct dependencies" is a substring of
    // "Indirect dependencies", so an unanchored regex would ambiguously
    // match both <dt> elements.
    expect(screen.getByText(/^Direct dependencies$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Indirect dependencies$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Affected controls$/i)).toBeInTheDocument()
    expect(screen.getByText(/^Potential GxP impact$/i)).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('renders every node id in each non-empty per-question breakdown list', () => {
    const { container } = render(
      <BlastRadiusPanel result={IMPACT_RESULT} loading={false} error={null} />,
    )
    for (const id of [
      ...IMPACT_RESULT.affected_requirements,
      ...IMPACT_RESULT.affected_tests,
      ...IMPACT_RESULT.affected_risks,
      ...IMPACT_RESULT.affected_systems,
    ]) {
      expect(container.textContent).toContain(id)
    }
  })

  it('renders an explicit none marker for an empty bucket rather than an empty region', () => {
    render(<BlastRadiusPanel result={IMPACT_RESULT} loading={false} error={null} />)
    // affected_changes is [] in IMPACT_RESULT.
    expect(screen.getAllByText(/^None$/).length).toBeGreaterThan(0)
  })

  it('renders an explicit none marker for a null highest_impact_downstream, not the string "null"', () => {
    render(<BlastRadiusPanel result={EMPTY_RESULT} loading={false} error={null} />)
    expect(screen.queryByText('null')).not.toBeInTheDocument()
    expect(screen.getAllByText(/^None$/).length).toBeGreaterThan(0)
  })

  it('renders an explicit no-downstream-impact message for an all-empty NONE result, not an error', () => {
    render(<BlastRadiusPanel result={EMPTY_RESULT} loading={false} error={null} />)
    expect(screen.getByText(/no downstream impact/i)).toBeInTheDocument()
    expect(screen.queryByText(/^error/i)).not.toBeInTheDocument()
  })

  it('renders a loading indicator when loading is true', () => {
    render(<BlastRadiusPanel result={null} loading={true} error={null} />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders the error text when error is non-null', () => {
    render(<BlastRadiusPanel result={null} loading={false} error="network down" />)
    expect(screen.getByText(/network down/i)).toBeInTheDocument()
  })

  it('renders the select-a-node prompt when result is null and not loading/erroring', () => {
    render(<BlastRadiusPanel result={null} loading={false} error={null} />)
    expect(screen.getByText(/select a node/i)).toBeInTheDocument()
  })

  it('issues no fetch when rendered in isolation', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<BlastRadiusPanel result={IMPACT_RESULT} loading={false} error={null} />)
    expect(fetchMock).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
