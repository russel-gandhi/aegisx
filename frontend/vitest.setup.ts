import '@testing-library/jest-dom'

// jsdom has no ResizeObserver; @xyflow/react's pane measurement relies on one to lay out
// nodes, so the route-render test suite needs a no-op stand-in to mount the canvas at all.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
}
