import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from '../App'
import { routes } from '../routes'

const BANNER_TEXT = 'PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE'

// One distinctive heading per route, asserted independently of the route table so a typo
// in one page's own heading can't accidentally make this test tautological.
const expectedHeadings: Record<string, string> = {
  '/': 'Command Centre',
  '/copilot': 'Ask GxP Copilot',
  '/audit-readiness': 'Audit Readiness',
  '/blast-radius': 'Blast Radius',
  '/suppliers': 'Supplier Intelligence',
  '/actions': 'Action / Approval Centre',
  '/assurance-lab': 'Assurance Lab',
  '/trust-centre': 'Trust Centre',
  '/inspection-simulator': 'Inspection Readiness Simulator',
}

describe('route table', () => {
  it('has exactly nine entries', () => {
    expect(routes).toHaveLength(9)
  })

  it('has unique paths', () => {
    const paths = routes.map((r) => r.path)
    expect(new Set(paths).size).toBe(paths.length)
  })
})

describe('route rendering', () => {
  for (const path of Object.keys(expectedHeadings)) {
    it(`renders the distinctive heading for ${path}`, () => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <AppShell />
        </MemoryRouter>,
      )
      expect(
        screen.getByRole('heading', { level: 1, name: expectedHeadings[path] }),
      ).toBeInTheDocument()
    })

    it(`shows the prototype banner on ${path}`, () => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <AppShell />
        </MemoryRouter>,
      )
      expect(screen.getByText(BANNER_TEXT)).toBeInTheDocument()
    })
  }

  it('renders a not-found page for an unknown path', () => {
    render(
      <MemoryRouter initialEntries={['/this-route-does-not-exist']}>
        <AppShell />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
  })

  it('mounts a React Flow canvas with placeholder nodes on /copilot', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/copilot']}>
        <AppShell />
      </MemoryRouter>,
    )
    expect(container.querySelector('.react-flow')).toBeTruthy()
    expect(container.querySelectorAll('.react-flow__node').length).toBeGreaterThan(0)
  })
})
