import { BrowserRouter, Routes, Route } from 'react-router-dom'
import PrototypeBanner from './components/PrototypeBanner'
import NavBar from './components/NavBar'
import RoleSelector from './components/RoleSelector'
import GuidedTourOverlay from './components/GuidedTourOverlay'
import { routes } from './routes'

function NotFound() {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">Page not found</h1>
      <p className="mt-2 text-slate-400">There's nothing at this address.</p>
    </div>
  )
}

// Factored out from <App> so the test suite can drive it with a MemoryRouter instead of
// the BrowserRouter used at runtime, without duplicating the route table wiring.
export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <PrototypeBanner />
      <NavBar />
      <RoleSelector />
      <GuidedTourOverlay />
      <main className="p-6">
        <Routes>
          {routes.map(({ path, Component }) => (
            <Route key={path} path={path} element={<Component />} />
          ))}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
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
