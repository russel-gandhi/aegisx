import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RoleSelector from '../components/RoleSelector'
import { AppShell } from '../App'
import {
  DEMO_IDENTITIES,
  getIdentity,
  setIdentity,
  identityHeaders,
} from '../lib/identity'
import { apiPost, ApiError } from '../lib/api'
import type { AssuranceCardData } from '../lib/api'
import { jsonResponse, stubAssuranceCardsFetch } from './helpers/sseFetch'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
  // Restore the default identity between tests so one test's `setIdentity`
  // call cannot leak into the next (this module's state is a singleton).
  setIdentity(DEMO_IDENTITIES[0])
})

describe('RoleSelector component', () => {
  it('renders the three Bible role labels', () => {
    render(<RoleSelector />)
    expect(screen.getByText('IT System Manager')).toBeInTheDocument()
    expect(screen.getByText('QA/Compliance')).toBeInTheDocument()
    expect(screen.getByText('Auditor')).toBeInTheDocument()
  })

  it('clicking a role updates getIdentity()', () => {
    render(<RoleSelector />)
    fireEvent.click(screen.getByText('Auditor'))
    expect(getIdentity().role).toBe('Auditor')
    expect(getIdentity().user_id).toBe('u-auditor-01')
  })

  it('marks the selected role aria-pressed and the others not', () => {
    render(<RoleSelector />)
    fireEvent.click(screen.getByText('QA/Compliance'))
    expect(screen.getByText('QA/Compliance').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('IT System Manager').getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByText('Auditor').getAttribute('aria-pressed')).toBe('false')
  })
})

describe('lib/identity', () => {
  it('identityHeaders() returns the currently selected role', () => {
    setIdentity(DEMO_IDENTITIES[2])
    expect(identityHeaders()).toEqual({
      'X-User-Id': DEMO_IDENTITIES[2].user_id,
      'X-User-Role': DEMO_IDENTITIES[2].role,
    })
  })

  it('falls back to the default identity for an unrecognised persisted role', async () => {
    window.localStorage.setItem(
      'aegisx.demo-identity',
      JSON.stringify({ user_id: 'someone', role: 'Not A Real Role' }),
    )
    vi.resetModules()
    const fresh = await import('../lib/identity')
    expect(fresh.getIdentity()).toEqual(DEMO_IDENTITIES[0])
  })
})

describe('lib/api apiPost / ApiError', () => {
  it('attaches both identity headers on an apiPost call', async () => {
    setIdentity(DEMO_IDENTITIES[1])
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await apiPost('/api/actions/some-id/approve')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = init.headers as Record<string, string>
    expect(headers['X-User-Id']).toBe(DEMO_IDENTITIES[1].user_id)
    expect(headers['X-User-Role']).toBe(DEMO_IDENTITIES[1].role)
  })

  it('ApiError from a 403 response carries the parsed status and detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Role Auditor may not approve actions' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiPost('/api/actions/some-id/approve')).rejects.toMatchObject({
      status: 403,
      detail: 'Role Auditor may not approve actions',
    })

    try {
      await apiPost('/api/actions/some-id/approve')
      throw new Error('expected apiPost to reject')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(403)
      expect((error as ApiError).detail).toBe('Role Auditor may not approve actions')
    }
  })
})

// Acceptance criterion: rendering FindingInvestigation with a stubbed 403
// from generateCapa shows the UI contract's permission sentence verbatim.
const FINDING_CARD: AssuranceCardData = {
  finding_id: 'A2-RBAC-TEST-01',
  claim: 'FIXTURE-CLAIM-for the RBAC-denial test',
  evidence_ids: [],
  regulatory_citations: ['FIXTURE-CITATION-ANNEX11-S4-DOC-001'],
  deterministic_check: {
    check_name: 'FIXTURE-CHECKFN-rbac-test',
    passed: false,
    db_record_found: true,
    opa_corroborated: true,
    opa_rule_ids: [],
  },
  confidence: 'MEDIUM',
  alcoa_score: {
    attributable: false,
    legible: true,
    contemporaneous: false,
    original: false,
    accurate: true,
    complete: true,
    consistent: true,
    enduring: true,
    available: true,
  },
  model_attribution: 'FIXTURE-MODEL-ID',
}

describe('FindingInvestigation Generate CAPA RBAC denial', () => {
  it('shows the UI contract permission sentence verbatim on a 403 from generateCapa', async () => {
    stubAssuranceCardsFetch({
      cards: [FINDING_CARD],
      graph: { system_id: 'GXP-MFG-DEMO-01', nodes: [], edges: [] },
      extraRoutes: [
        {
          match: (url, init) => url.includes('/generate-capa') && init?.method === 'POST',
          respond: () =>
            jsonResponse(
              { detail: 'Role Auditor may not trigger A7 Remediation' },
              { ok: false, status: 403 },
            ),
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/findings']}>
        <AppShell />
      </MemoryRouter>,
    )

    const button = await screen.findByRole('button', { name: 'Generate CAPA' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(
        screen.getByText(
          "You don't have permission to approve this action — only IT System Manager can approve GxP-relevant writes.",
        ),
      ).toBeInTheDocument()
    })
  })
})
