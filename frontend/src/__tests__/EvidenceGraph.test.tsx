import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

function stubFetchOnce(response: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: async () => response,
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
