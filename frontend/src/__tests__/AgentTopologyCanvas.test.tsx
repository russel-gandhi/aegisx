import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import AgentTopologyCanvas from '../components/AgentTopologyCanvas'

// Phase 6 (D-02/D-03, UI-04): AgentTopologyCanvas's live node-status
// coloring and the permanent "not exercised this query type" dimming.
// Node lookup mirrors EvidenceGraph.test.tsx's own convention -- find the
// `.react-flow__node` whose textContent includes the node id, rather than
// depending on an undocumented `data-id` attribute.

function findNode(container: HTMLElement, id: string): Element {
  const node = Array.from(container.querySelectorAll('.react-flow__node')).find((el) =>
    el.textContent?.includes(id),
  )
  if (node === undefined) {
    throw new Error(`node ${id} not found`)
  }
  return node
}

describe('AgentTopologyCanvas', () => {
  it('renders every node waiting by default (pre-query loading/idle state)', () => {
    const { container } = render(<AgentTopologyCanvas />)
    for (const id of ['C2', 'A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'C1', 'A7', 'C3']) {
      const node = findNode(container, id)
      expect(node.className).toContain('border-white/15')
      expect(node.className).toContain('bg-white/[0.05]')
    }
  })

  it('A1, A3-A6, C2, A7, C3 carry opacity-40 in every rendered state', () => {
    const { container } = render(
      <AgentTopologyCanvas
        nodeStatus={{ A0: 'complete', A2: 'complete', C1: 'complete' }}
      />,
    )
    for (const id of ['C2', 'A1', 'A3', 'A4', 'A5', 'A6', 'A7', 'C3']) {
      expect(findNode(container, id).className).toContain('opacity-40')
    }
    // The real-path nodes for this query type are never dimmed.
    for (const id of ['A0', 'A2', 'C1']) {
      expect(findNode(container, id).className).not.toContain('opacity-40')
    }
  })

  it('renders the literal "A1, A3–A6 not yet implemented (v2)" note', () => {
    const { container } = render(<AgentTopologyCanvas />)
    expect(container.textContent).toContain('A1, A3–A6 not yet implemented (v2)')
  })

  it('colors A0/A2 running and C1 waiting on stream open', () => {
    const { container } = render(<AgentTopologyCanvas nodeStatus={{ A0: 'running', A2: 'running' }} />)
    expect(findNode(container, 'A0').className).toContain('border-amber')
    expect(findNode(container, 'A2').className).toContain('border-amber')
    expect(findNode(container, 'C1').className).toContain('border-white/15')
  })

  it('colors C1 running on the first card, then all three complete on the terminal frame', () => {
    const { container, rerender } = render(
      <AgentTopologyCanvas nodeStatus={{ A0: 'running', A2: 'running' }} />,
    )
    rerender(
      <AgentTopologyCanvas nodeStatus={{ A0: 'running', A2: 'running', C1: 'running' }} />,
    )
    expect(findNode(container, 'C1').className).toContain('border-amber')

    rerender(
      <AgentTopologyCanvas
        nodeStatus={{ A0: 'complete', A2: 'complete', C1: 'complete' }}
      />,
    )
    for (const id of ['A0', 'A2', 'C1']) {
      expect(findNode(container, id).className).toContain('border-mint')
    }
  })

  it('does not render the disconnected banner by default', () => {
    const { queryByTestId } = render(<AgentTopologyCanvas />)
    expect(queryByTestId('topology-disconnected-banner')).toBeNull()
  })

  it('renders the disconnected banner and leaves nodes at their last-known color when disconnected', () => {
    const { getByTestId, container } = render(
      <AgentTopologyCanvas nodeStatus={{ A0: 'running', A2: 'running' }} disconnected />,
    )
    expect(getByTestId('topology-disconnected-banner').textContent).toContain(
      'Live agent state disconnected',
    )
    expect(findNode(container, 'A0').className).toContain('border-amber')
  })
})
