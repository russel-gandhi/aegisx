import { BrowserRouter, Routes, Route } from 'react-router-dom'
import PrototypeBanner from './components/PrototypeBanner'
import NavBar from './components/NavBar'
import RoleSelector from './components/RoleSelector'
import GuidedTourOverlay from './components/GuidedTourOverlay'
import { routes } from './routes'

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
        <PrototypeBanner />
        <NavBar />
        <RoleSelector />
        <GuidedTourOverlay />
        <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:py-10">
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
