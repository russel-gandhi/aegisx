import { NavLink } from 'react-router-dom'
import { routes } from '../routes'

export default function NavBar() {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-slate-800 bg-slate-900 px-4 py-2">
      {routes.map((route) => (
        <NavLink
          key={route.path}
          to={route.path}
          end={route.path === '/'}
          className={({ isActive }) =>
            `rounded px-3 py-1.5 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`
          }
        >
          {route.label}
        </NavLink>
      ))}
    </nav>
  )
}
