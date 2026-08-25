import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, waitFor, fireEvent } from '@testing-library/react'
import Actions from '../pages/Actions'
import { ApiError, type ActionProposalData, type ActionProposalsResponse } from '../lib/api'
import type { CopilotStreamHandlers } from '../lib/ws'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    fetchActionProposals: vi.fn(),
    approveAction: vi.fn(),
    rejectAction: vi.fn(),
  }
})

vi.mock('../lib/ws', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/ws')>()
  return {
    ...actual,
    connectCopilotStream: vi.fn(),
  }
})

import { fetchActionProposals, approveAction, rejectAction } from '../lib/api'
import { connectCopilotStream } from '../lib/ws'

const mockFetchActionProposals = vi.mocked(fetchActionProposals)
const mockApproveAction = vi.mocked(approveAction)
const mockRejectAction = vi.mocked(rejectAction)
const mockConnectCopilotStream = vi.mocked(connectCopilotStream)

let capturedHandlers: CopilotStreamHandlers | null = null

function stubStream() {
  mockConnectCopilotStream.mockImplementation((_sessionId, handlers) => {
    capturedHandlers = handlers
    return { close: vi.fn(), send: vi.fn() }
  })
}

function respond(response: ActionProposalsResponse) {
  mockFetchActionProposals.mockResolvedValue(response)
}

const BASE_PROPOSAL: ActionProposalData = {
  id: 'PROP-BASE-01',
  action_type: 'CREATE_CAPA_RECORD',
  category: 'GXP_RELEVANT_WRITE',
  target_system: 'GXP-MFG-DEMO-01',
  payload: { note: 'fixture payload' },
  status: 'PENDING_APPROVAL',
  justification: 'FIXTURE-JUSTIFICATION-the periodic evaluation gap',
  finding_id: 'A2-FIXTURE-01',
  model_id: 'FIXTURE-MODEL-ID',
  created_at: '2026-01-01T00:00:00Z',
  approved_by: null,
  approved_at: null,
  execution_result: null,
}

function makeProposal(overrides: Partial<ActionProposalData>): ActionProposalData {
  return { ...BASE_PROPOSAL, ...overrides }
}

beforeEach(() => {
  capturedHandlers = null
  mockFetchActionProposals.mockReset()
  mockApproveAction.mockReset()
  mockRejectAction.mockReset()
  mockConnectCopilotStream.mockReset()
  stubStream()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Actions page states', () => {
  it('renders the loading state string', () => {
    mockFetchActionProposals.mockReturnValue(new Promise(() => {}))
    render(<Actions />)
    expect(screen.getByText('Loading pending actions...')).toBeInTheDocument()
  })

  it('renders the fetch-error state string', async () => {
    mockFetchActionProposals.mockRejectedValue(new Error('network down'))
    render(<Actions />)
    await waitFor(() => {
      expect(
        screen.getByText("Couldn't load pending actions — check your connection and retry."),
      ).toBeInTheDocument()
    })
  })

  it('renders the empty state heading and body verbatim', async () => {
    respond({ proposals: [] })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getByText('No pending actions')).toBeInTheDocument()
    })
    expect(
      screen.getByText(
        'All caught up — proposed actions will appear here as A7 generates them, and this list updates live.',
      ),
    ).toBeInTheDocument()
  })

  it('renders "Pending Actions (0)" for an empty queue', async () => {
    respond({ proposals: [] })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getByText('Pending Actions (0)')).toBeInTheDocument()
    })
  })

  it('renders "Pending Actions (3)" for a three-proposal fixture', async () => {
    respond({
      proposals: [
        makeProposal({ id: 'P1' }),
        makeProposal({ id: 'P2' }),
        makeProposal({ id: 'P3' }),
      ],
    })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getByText('Pending Actions (3)')).toBeInTheDocument()
    })
  })

  it('renders a populated queue ordered oldest-first by created_at', async () => {
    respond({
      proposals: [
        makeProposal({ id: 'NEWEST', created_at: '2026-03-01T00:00:00Z' }),
        makeProposal({ id: 'OLDEST', created_at: '2026-01-01T00:00:00Z' }),
        makeProposal({ id: 'MIDDLE', created_at: '2026-02-01T00:00:00Z' }),
      ],
    })
    const { container } = render(<Actions />)
    await waitFor(() => {
      expect(container.querySelectorAll('[data-testid="action-proposal-card"]').length).toBe(3)
    })
    // Assert DOM order matches OLDEST, MIDDLE, NEWEST by created_at.
    const cards = container.querySelectorAll('[data-testid="action-proposal-card"]')
    expect(cards[0].getAttribute('data-status')).toBe('PENDING_APPROVAL')
    expect(cards[0].textContent).toContain('OLDEST')
    expect(cards[1].textContent).toContain('MIDDLE')
    expect(cards[2].textContent).toContain('NEWEST')
  })

  it('renders "Not provided" exactly twice for a fixture with null justification and null category', async () => {
    respond({
      proposals: [
        makeProposal({
          justification: null,
          category: null as unknown as string,
        }),
      ],
    })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getAllByText('Not provided').length).toBe(2)
    })
  })

  it('renders a large payload inside a scrollable, max-height <pre>', async () => {
    const largePayload = { data: 'x'.repeat(5000) }
    respond({ proposals: [makeProposal({ payload: largePayload })] })
    const { container } = render(<Actions />)
    await waitFor(() => {
      const pre = container.querySelector('pre')
      expect(pre).not.toBeNull()
      expect(pre?.className).toContain('max-h-48')
      expect(pre?.className).toContain('overflow-auto')
      expect(pre?.textContent).toContain('x'.repeat(100))
    })
  })
})

describe('Actions page live updates', () => {
  it('appends exactly one card for a new action_proposal_created frame, and a duplicate does not add a second', async () => {
    respond({ proposals: [] })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getByText('Pending Actions (0)')).toBeInTheDocument()
    })

    const pushed = makeProposal({ id: 'PUSHED-01' })
    act(() => {
      capturedHandlers?.onFrame({ event: 'action_proposal_created', proposal: pushed })
    })
    await waitFor(() => {
      expect(screen.getByText('Pending Actions (1)')).toBeInTheDocument()
    })

    act(() => {
      capturedHandlers?.onFrame({ event: 'action_proposal_created', proposal: pushed })
    })
    // A duplicate frame for the same id must not double-render.
    expect(screen.getByText('Pending Actions (1)')).toBeInTheDocument()
  })

  it('renders the live-updates-degraded copy on a socket close', async () => {
    respond({ proposals: [] })
    render(<Actions />)
    await waitFor(() => {
      expect(screen.getByText('Pending Actions (0)')).toBeInTheDocument()
    })

    act(() => {
      capturedHandlers?.onClose?.()
    })

    await waitFor(() => {
      expect(
        screen.getByText('Live updates unavailable — refresh to see new actions.'),
      ).toBeInTheDocument()
    })
  })
})

describe('Actions page Approve / Reject', () => {
  it('disables both buttons and shows "Approving..." while approve is in flight', async () => {
    respond({ proposals: [makeProposal({})] })
    mockApproveAction.mockReturnValue(new Promise(() => {}))
    render(<Actions />)

    const approveButton = await screen.findByRole('button', { name: 'Approve Action' })
    const rejectButton = screen.getByRole('button', { name: 'Reject Action' })
    fireEvent.click(approveButton)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approving...' })).toBeDisabled()
    })
    expect(rejectButton).toBeDisabled()
  })

  it('renders the permission sentence on a 403 from approveAction, leaving the proposal PENDING_APPROVAL', async () => {
    respond({ proposals: [makeProposal({})] })
    mockApproveAction.mockRejectedValue(
      new ApiError(403, 'Role Auditor may not approve actions', 'POST failed with status 403'),
    )
    const { container } = render(<Actions />)

    const approveButton = await screen.findByRole('button', { name: 'Approve Action' })
    fireEvent.click(approveButton)

    await waitFor(() => {
      expect(
        screen.getByText(
          "You don't have permission to approve this action — only IT System Manager can approve GxP-relevant writes.",
        ),
      ).toBeInTheDocument()
    })
    const card = container.querySelector('[data-testid="action-proposal-card"]')
    expect(card?.getAttribute('data-status')).toBe('PENDING_APPROVAL')
  })

  it('renders the generic decision-failure copy on a 500 from approveAction', async () => {
    respond({ proposals: [makeProposal({})] })
    mockApproveAction.mockRejectedValue(
      new ApiError(500, 'internal error', 'POST failed with status 500'),
    )
    render(<Actions />)

    const approveButton = await screen.findByRole('button', { name: 'Approve Action' })
    fireEvent.click(approveButton)

    await waitFor(() => {
      expect(screen.getByText("Couldn't record your decision — try again.")).toBeInTheDocument()
    })
  })

  it('shows the destructive Reject confirmation with the proposal\'s own action_type and target_system', async () => {
    respond({
      proposals: [
        makeProposal({ action_type: 'DRAFT_SERVICENOW_TICKET', target_system: 'BUS-IT-DEMO-02' }),
      ],
    })
    render(<Actions />)

    const rejectButton = await screen.findByRole('button', { name: 'Reject Action' })
    fireEvent.click(rejectButton)

    expect(
      screen.getByText(
        'Reject Action: Reject this DRAFT_SERVICENOW_TICKET on BUS-IT-DEMO-02? It will not be executed. This decision is recorded in the audit trail and cannot be undone.',
      ),
    ).toBeInTheDocument()
  })

  it('replaces the proposal with the server record after a successful approve (no optimistic flip)', async () => {
    const proposal = makeProposal({ id: 'PROP-APPROVE-01' })
    respond({ proposals: [proposal] })
    mockApproveAction.mockResolvedValue({ ...proposal, status: 'APPROVED', approved_by: 'u-itsm-01' })
    const { container } = render(<Actions />)

    const approveButton = await screen.findByRole('button', { name: 'Approve Action' })
    fireEvent.click(approveButton)

    await waitFor(() => {
      const card = container.querySelector('[data-testid="action-proposal-card"]')
      expect(card?.getAttribute('data-status')).toBe('APPROVED')
    })
  })
})
