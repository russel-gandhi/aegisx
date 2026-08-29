import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import AutoNavigateNotice, {
  AUTO_NAVIGATE_DELAY_MS,
  STAY_HERE_LABEL,
  CANCELLED_COPY,
  autoNavigateCopy,
} from '../components/AutoNavigateNotice'
import type { NavigationTarget } from '../lib/api'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function fixtureTarget(overrides: Partial<NavigationTarget> = {}): NavigationTarget {
  return {
    kind: 'document',
    target_id: 'DOC-A',
    label: 'Fixture Validation Protocol',
    system_id: 'GXP-MFG-DEMO-01',
    reason: 'single unambiguous document citation',
    ...overrides,
  }
}

beforeEach(() => {
  mockNavigate.mockClear()
  vi.useFakeTimers()
})

afterEach(() => {
  cleanup()
  vi.runOnlyPendingTimers()
  vi.useRealTimers()
})

describe('AutoNavigateNotice -- notice copy and Stay here button', () => {
  it('renders the notice copy with destination and label interpolated, plus a focusable Stay here button', () => {
    const target = fixtureTarget()
    render(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)

    const notice = screen.getByTestId('auto-navigate-notice')
    expect(notice.textContent).toContain(autoNavigateCopy('Knowledge', target.label))
    const button = screen.getByTestId('auto-navigate-stay-here')
    expect(button.tagName).toBe('BUTTON')
    expect(button.textContent).toBe(STAY_HERE_LABEL)
  })
})

describe('AutoNavigateNotice -- accessibility announcement', () => {
  it('carries role="status" and aria-live="polite"', () => {
    render(<AutoNavigateNotice target={fixtureTarget()} armed onCancelled={vi.fn()} />)
    const notice = screen.getByTestId('auto-navigate-notice')
    expect(notice.getAttribute('role')).toBe('status')
    expect(notice.getAttribute('aria-live')).toBe('polite')
  })
})

describe('AutoNavigateNotice -- fires navigate() after the delay', () => {
  it('calls navigate() exactly once with the resolved href after AUTO_NAVIGATE_DELAY_MS', () => {
    const target = fixtureTarget()
    render(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)

    expect(mockNavigate).not.toHaveBeenCalled()
    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)

    expect(mockNavigate).toHaveBeenCalledTimes(1)
    expect(mockNavigate).toHaveBeenCalledWith('/knowledge?system=GXP-MFG-DEMO-01&document=DOC-A')
  })
})

describe('AutoNavigateNotice -- Stay here cancels', () => {
  it('never calls navigate() and replaces the notice with CANCELLED_COPY', () => {
    const onCancelled = vi.fn()
    render(<AutoNavigateNotice target={fixtureTarget()} armed onCancelled={onCancelled} />)

    fireEvent.click(screen.getByTestId('auto-navigate-stay-here'))
    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)

    expect(mockNavigate).not.toHaveBeenCalled()
    expect(onCancelled).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('auto-navigate-notice-cancelled').textContent).toBe(CANCELLED_COPY)
    expect(screen.queryByTestId('auto-navigate-notice')).toBeNull()
  })
})

describe('AutoNavigateNotice -- armed false', () => {
  it('renders nothing and arms no timer even when target is present', () => {
    const { container } = render(
      <AutoNavigateNotice target={fixtureTarget()} armed={false} onCancelled={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})

describe('AutoNavigateNotice -- unrecognised kind yields a null navigationHref', () => {
  it('renders nothing and arms no timer', () => {
    const target = fixtureTarget({ kind: 'unknown_kind' as unknown as NavigationTarget['kind'] })
    const { container } = render(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)
    expect(container.firstChild).toBeNull()
    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})

describe('AutoNavigateNotice -- unmount clears the timer', () => {
  it('never calls navigate() after unmount, with no act/state-update warning', () => {
    const { unmount } = render(<AutoNavigateNotice target={fixtureTarget()} armed onCancelled={vi.fn()} />)
    unmount()
    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})

describe('AutoNavigateNotice -- re-render arms exactly one timer', () => {
  it('produces exactly one navigate() call across multiple re-renders with the same props', () => {
    const target = fixtureTarget()
    const { rerender } = render(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)
    rerender(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)
    rerender(<AutoNavigateNotice target={target} armed onCancelled={vi.fn()} />)

    vi.advanceTimersByTime(AUTO_NAVIGATE_DELAY_MS)

    expect(mockNavigate).toHaveBeenCalledTimes(1)
  })
})
