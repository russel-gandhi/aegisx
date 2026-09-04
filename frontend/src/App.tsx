import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import PrototypeBanner from './components/PrototypeBanner'
import NavBar from './components/NavBar'
import RoleSelector from './components/RoleSelector'
import GuidedTourOverlay from './components/GuidedTourOverlay'
import { routes } from './routes'

// React Router does not reset scroll position on navigation (a well-known
// gap, not an oversight this codebase introduced) -- without this, a user
// scrolled halfway down a long page who clicks a nav link, or the Guided
// Tour navigating between steps, lands on the next page already scrolled
// to wherever the previous page happened to leave off. Route-change only:
// deliberately not on every render, and not on hash-only changes within
// the same path.
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <h1 className="text-2xl font-semibold text-ink">Page not found</h1>
      <p className="mt-2 text-ink-muted">There's nothing at this address.</p>
    </div>
  )
}

// Factored out from <App> so the test suite can drive it with a MemoryRouter instead of
// the BrowserRouter used at runtime, without duplicating the route table wiring.
export function AppShell() {
  return (
    <div className="relative min-h-screen bg-canvas text-ink">
      <div className="app-ambient" aria-hidden="true" />
      <div className="relative z-10">
        <ScrollToTop />
        <PrototypeBanner />
        <NavBar />
        <RoleSelector />
        <GuidedTourOverlay />
        <main className="mx-auto max-w-[1400px] px-4 py-8 pb-28 sm:px-6 lg:py-10 lg:pb-28">
          <Routes>
            {routes.map(({ path, Component }) => (
              <Route key={path} path={path} element={<Component />} />
            ))}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

export default App
