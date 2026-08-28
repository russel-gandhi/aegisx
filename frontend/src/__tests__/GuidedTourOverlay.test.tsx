import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import GuidedTourOverlay from '../components/GuidedTourOverlay'

// react-joyride's real implementation relies on floating-ui positioning,
// scroll-into-view, and portal rendering that jsdom does not fully support
// (no layout engine) -- exactly the "deceptive complexity" 06-RESEARCH.md's
// Don't Hand-Roll section says the library exists to absorb. Mocking the
// library itself here isolates GuidedTourOverlay's own business logic
// (route navigation, the D-09 idempotency guard, target-not-found handling)
// under test, the same way Copilot.test.tsx mocks `connectCopilotStream`
// rather than exercising a real WebSocket. Production code still renders
// the real `<Joyride>` -- only this test substitutes a controllable stub.
vi.mock('react-joyride', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-joyride')>()
  return {
    ...actual,
    Joyride: (props: {
      run: boolean
      stepIndex: number
      steps: Array<{ target: string; title?: string; content?: string }>
      onEvent: (data: unknown) => void
    }) => {
      if (!props.run) return null
      const currentStep = props.steps[props.stepIndex]
      return (
        <div data-testid="mock-joyride">
          <p data-testid="mock-joyride-target">{currentStep?.target}</p>
          <p data-testid="mock-joyride-title">{currentStep?.title}</p>
          <button
            type="button"
            data-testid="mock-joyride-next"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.STEP_AFTER,
                action: actual.ACTIONS.NEXT,
                status: actual.STATUS.RUNNING,
              })
            }
          >
            Next
          </button>
          <button
            type="button"
            data-testid="mock-joyride-target-not-found"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.TARGET_NOT_FOUND,
                action: actual.ACTIONS.UPDATE,
                status: actual.STATUS.RUNNING,
              })
            }
          >
            Simulate target not found
          </button>
          <button
            type="button"
            data-testid="mock-joyride-finish"
            onClick={() =>
              props.onEvent({
                type: actual.EVENTS.TOUR_END,
                action: actual.ACTIONS.CLOSE,
                status: actual.STATUS.FINISHED,
              })
            }
          >
            Finish
          </button>
        </div>
      )
    },
  }
})

function LocationProbe() {
  return null
}

function renderOverlay(initialEntries: string[] = ['/copilot']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <GuidedTourOverlay />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('GuidedTourOverlay', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the entry banner and starts the tour', () => {
    renderOverlay()

    expect(screen.getByTestId('start-guided-tour')).toHaveTextContent('Start Guided Tour')
    expect(screen.queryByTestId('mock-joyride')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('start-guided-tour'))

    expect(screen.getByTestId('mock-joyride')).toBeInTheDocument()
    expect(screen.getByTestId('mock-joyride-target')).toHaveTextContent(
      '[data-tour="readiness-dial"]',
    )
    expect(screen.queryByTestId('start-guided-tour')).not.toBeInTheDocument()
  })

  it('resets to the entry banner when the tour finishes', () => {
    renderOverlay()
    fireEvent.click(screen.getByTestId('start-guided-tour'))
    fireEvent.click(screen.getByTestId('mock-joyride-finish'))

    expect(screen.getByTestId('start-guided-tour')).toBeInTheDocument()
    expect(screen.queryByTestId('mock-joyride')).not.toBeInTheDocument()
  })

  it('shows a persistent note rather than crashing or silently skipping when a target is not found', () => {
    renderOverlay()
    fireEvent.click(screen.getByTestId('start-guided-tour'))
    fireEvent.click(screen.getByTestId('mock-joyride-target-not-found'))

    expect(screen.getByTestId('tour-target-not-found-note')).toBeInTheDocument()
  })
})
