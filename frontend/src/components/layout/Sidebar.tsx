import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderKanban,
  Workflow,
  Settings,
  LogOut,
  Eye,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/projects', icon: FolderKanban, label: 'Projects' },
  { to: '/workflows', icon: Workflow, label: 'Workflows' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const { logout, user } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside className="w-56 bg-gray-900 text-gray-100 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-700">
        <Eye className="w-7 h-7 text-blue-400" />
        <span className="text-lg font-semibold tracking-tight">VisionForge</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-4 border-t border-gray-700">
        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
        <button
          onClick={handleLogout}
          className="mt-2 flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
