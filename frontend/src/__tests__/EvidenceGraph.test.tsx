import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from '../App'

const SAMPLE_RESPONSE = {
  system_id: 'GXP-MFG-DEMO-01',
  nodes: [
    { node_id: 'SYSTEM:GXP-MFG-DEMO-01', node_type: 'SYSTEM', entity_id: 'GXP-MFG-DEMO-01', properties: {} },
    { node_id: 'REQUIREMENT:URS-042', node_type: 'REQUIREMENT', entity_id: 'URS-042', properties: {} },
  ],
  edges: [
    { source_id: 'REQUIREMENT:URS-042', target_id: 'SYSTEM:GXP-MFG-DEMO-01', relation_type: 'VERIFIED_BY' },
  ],
}

// Plan 04-05: a richer fixture carrying a node with properties, used by
// the click-through / node-detail / blast-radius tests below.
const CLICK_THROUGH_RESPONSE = {
  system_id: 'GXP-MFG-DEMO-01',
  nodes: [
    { node_id: 'SYSTEM:GXP-MFG-DEMO-01', node_type: 'SYSTEM', entity_id: 'GXP-MFG-DEMO-01', properties: {} },
    {
      node_id: 'REQUIREMENT:URS-042',
      node_type: 'REQUIREMENT',
      entity_id: 'URS-042',
      properties: { status: 'approved', version: 3 },
    },
    {
      node_id: 'CHANGE:CR-2026-089',
      node_type: 'CHANGE',
      entity_id: 'CR-2026-089',
      properties: { description: 'Update deviation workflow', status: 'IMPLEMENTED' },
    },
  ],
  edges: [
    { source_id: 'REQUIREMENT:URS-042', target_id: 'SYSTEM:GXP-MFG-DEMO-01', relation_type: 'VERIFIED_BY' },
  ],
}

const BLAST_RADIUS_RESPONSE = {
  system_id: 'GXP-MFG-DEMO-01',
  source_node_id: 'CHANGE:CR-2026-089',
  direct_dependencies: [
    'REQUIREMENT:URS-042',
    'TEST_CASE:TC-001',
    'RISK:RA-001',
    'SYSTEM:GXP-MFG-DEMO-01',
  ],
  indirect_dependencies: ['REQUIREMENT:URS-043', 'TEST_CASE:TC-002'],
  affected_requirements: ['REQUIREMENT:URS-042'],
  affected_tests: ['TEST_CASE:TC-001'],
  affected_risks: ['RISK:RA-001'],
  affected_changes: [],
  affected_controls: [],
  affected_systems: ['SYSTEM:GXP-MFG-DEMO-01'],
  potential_gxp_impact: 'HIGH',
  highest_impact_downstream: 'REQUIREMENT:URS-042',
}

const SECOND_BLAST_RADIUS_RESPONSE = {
  ...BLAST_RADIUS_RESPONSE,
  source_node_id: 'REQUIREMENT:URS-042',
  direct_dependencies: ['SYSTEM:GXP-MFG-DEMO-01'],
  indirect_dependencies: [],
  potential_gxp_impact: 'MEDIUM',
}

function stubFetchOnce(response: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: async () => response,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// Routes the fetch stub by requested URL, per the plan's <behavior>
// instruction: the graph and blast-radius calls must be able to return
// different fixtures. `blastRadiusReject` simulates a rejected fetch;
// `secondBlastRadius` lets a second click return a different body.
function stubGraphAndBlastRadius(options?: {
  blastRadiusReject?: boolean
  secondBlastRadius?: unknown
}) {
  let blastCallCount = 0
  const fetchMock = vi.fn((url: string) => {
    if (url.includes('/blast-radius')) {
      blastCallCount += 1
      if (options?.blastRadiusReject) {
        return Promise.reject(new Error('network down'))
      }
      const body =
        blastCallCount > 1 && options?.secondBlastRadius
          ? options.secondBlastRadius
          : BLAST_RADIUS_RESPONSE
      return Promise.resolve({ ok: true, status: 200, json: async () => body })
    }
    if (url.includes('/evidence-graph')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => CLICK_THROUGH_RESPONSE })
    }
    return Promise.reject(new Error(`unstubbed fetch: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('/blast-radius', () => {
  it('renders a react-flow container with two nodes labelled by node_id', async () => {
    stubFetchOnce(SAMPLE_RESPONSE)

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelector('.react-flow')).toBeTruthy()
    })
    expect(container.querySelectorAll('.react-flow__node').length).toBe(2)
    expect(container.textContent).toContain('SYSTEM:GXP-MFG-DEMO-01')
    expect(container.textContent).toContain('REQUIREMENT:URS-042')
  })

  it('issues the fetch against the GXP-MFG-DEMO-01 evidence-graph URL', async () => {
    const fetchMock = stubFetchOnce(SAMPLE_RESPONSE)

    render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    const calledUrl = fetchMock.mock.calls[0][0] as string
    expect(calledUrl.endsWith('/api/systems/GXP-MFG-DEMO-01/evidence-graph')).toBe(true)
  })

  it('shows a loading state while the fetch is unresolved, then clears it', async () => {
    let resolveFetch: (value: unknown) => void = () => {}
    const pending = new Promise((resolve) => {
      resolveFetch = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(
        pending.then(() => ({
          ok: true,
          status: 200,
          json: async () => SAMPLE_RESPONSE,
        })),
      ),
    )

    render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    resolveFetch(undefined)

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })
  })

  it('renders a visible error message on a rejected fetch and does not throw', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })

  it('renders an explicit empty-state message for a zero-node response', async () => {
    stubFetchOnce({ system_id: 'BUS-IT-DEMO-02', nodes: [], edges: [] })

    render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/rebuild/i)).toBeInTheDocument()
    })
  })
})

// Plan 04-05: node click-through, the impact panel, and the ?node= deep
// link. `BlastRadiusPanel`'s own rendering behavior is covered by
// BlastRadiusPanel.test.tsx; these tests cover only the wiring between
// the click, the fetch, and what appears on the page.
describe('/blast-radius node click-through', () => {
  it('shows the select-a-node prompt and issues no blast-radius request before any click', async () => {
    const fetchMock = stubGraphAndBlastRadius()

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node').length).toBe(3)
    })

    // Scoped to the BlastRadiusPanel prompt specifically -- React Flow's
    // own hidden a11y description text ("Press enter or space to select a
    // node...") also matches an unscoped /select a node/i query.
    const blastPrompt = Array.from(container.querySelectorAll('p')).find((el) =>
      el.textContent?.includes('Select a node on the graph to see its blast radius.'),
    )
    expect(blastPrompt).toBeTruthy()
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes('/blast-radius'))).toBe(
      false,
    )
  })

  it('clicking a react-flow node issues one blast-radius request with the url-encoded node id and shows the returned counts', async () => {
    const fetchMock = stubGraphAndBlastRadius()

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node').length).toBe(3)
    })

    const changeNode = Array.from(container.querySelectorAll('.react-flow__node')).find((el) =>
      el.textContent?.includes('CHANGE:CR-2026-089'),
    )
    expect(changeNode).toBeTruthy()
    fireEvent.click(changeNode as Element)

    await waitFor(() => {
      const blastCalls = fetchMock.mock.calls.filter((call) =>
        String(call[0]).includes('/blast-radius'),
      )
      expect(blastCalls.length).toBe(1)
      expect(String(blastCalls[0][0])).toContain('node_id=CHANGE%3ACR-2026-089')
    })

    await waitFor(() => {
      expect(screen.getByText('HIGH')).toBeInTheDocument()
    })
  })

  it('clicking a second node issues a second request for that node and replaces the displayed result', async () => {
    const fetchMock = stubGraphAndBlastRadius({ secondBlastRadius: SECOND_BLAST_RADIUS_RESPONSE })

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node').length).toBe(3)
    })

    const nodesEls = Array.from(container.querySelectorAll('.react-flow__node'))
    const changeNode = nodesEls.find((el) => el.textContent?.includes('CHANGE:CR-2026-089'))
    fireEvent.click(changeNode as Element)

    await waitFor(() => {
      expect(screen.getByText('HIGH')).toBeInTheDocument()
    })

    const reqNode = nodesEls.find((el) => el.textContent?.includes('REQUIREMENT:URS-042'))
    fireEvent.click(reqNode as Element)

    await waitFor(() => {
      const blastCalls = fetchMock.mock.calls.filter((call) =>
        String(call[0]).includes('/blast-radius'),
      )
      expect(blastCalls.length).toBe(2)
      expect(String(blastCalls[1][0])).toContain('node_id=REQUIREMENT%3AURS-042')
    })

    await waitFor(() => {
      expect(screen.getByText('MEDIUM')).toBeInTheDocument()
    })
  })

  it("NodeDetailPanel shows the clicked node's type, entity id and each property key/value pair", async () => {
    stubGraphAndBlastRadius()

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node').length).toBe(3)
    })

    const changeNode = Array.from(container.querySelectorAll('.react-flow__node')).find((el) =>
      el.textContent?.includes('CHANGE:CR-2026-089'),
    )
    fireEvent.click(changeNode as Element)

    await waitFor(() => {
      const panel = container.querySelector('[data-testid="node-detail-panel"]')
      expect(panel).toBeTruthy()
      expect(panel?.textContent).toContain('CHANGE')
      expect(panel?.textContent).toContain('CR-2026-089')
      expect(panel?.textContent).toContain('description')
      expect(panel?.textContent).toContain('Update deviation workflow')
      expect(panel?.textContent).toContain('IMPLEMENTED')
    })
  })

  it('pre-selects the node from a ?node= deep link and issues one request on mount without a click', async () => {
    const fetchMock = stubGraphAndBlastRadius()

    render(
      <MemoryRouter initialEntries={['/blast-radius?node=CHANGE%3ACR-2026-089']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      const blastCalls = fetchMock.mock.calls.filter((call) =>
        String(call[0]).includes('/blast-radius'),
      )
      expect(blastCalls.length).toBe(1)
      expect(String(blastCalls[0][0])).toContain('node_id=CHANGE%3ACR-2026-089')
    })

    await waitFor(() => {
      expect(screen.getByText('HIGH')).toBeInTheDocument()
    })
  })

  it('a rejected blast-radius fetch renders the panel error state while the graph canvas stays rendered', async () => {
    stubGraphAndBlastRadius({ blastRadiusReject: true })

    const { container } = render(
      <MemoryRouter initialEntries={['/blast-radius']}>
        <AppShell />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node').length).toBe(3)
    })

    const changeNode = Array.from(container.querySelectorAll('.react-flow__node')).find((el) =>
      el.textContent?.includes('CHANGE:CR-2026-089'),
    )
    fireEvent.click(changeNode as Element)

    await waitFor(() => {
      const panel = container.querySelector('[data-testid="blast-radius-panel"]')
      expect(panel).toBeFalsy()
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
    expect(container.querySelector('.react-flow')).toBeTruthy()
  })
})
