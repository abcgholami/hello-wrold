import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderKanban, Image, Brain, Zap, Plus } from 'lucide-react'
import { coreApi } from '../api/client'
import { useAuthStore } from '../store/authStore'

interface Stats {
  projects: number
  images: number
  trainingJobs: number
  endpoints: number
}

export function Dashboard() {
  const { user } = useAuthStore()
  const [recentProjects, setRecentProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await coreApi.get('/projects', { params: { org_id: 'default' } })
        setRecentProjects(res.data.slice(0, 6))
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const stats = [
    { label: 'Projects', value: recentProjects.length, icon: FolderKanban, color: 'text-blue-500', bg: 'bg-blue-50' },
    { label: 'Images Uploaded', value: '—', icon: Image, color: 'text-purple-500', bg: 'bg-purple-50' },
    { label: 'Training Runs', value: '—', icon: Brain, color: 'text-green-500', bg: 'bg-green-50' },
    { label: 'Active Endpoints', value: '—', icon: Zap, color: 'text-orange-500', bg: 'bg-orange-50' },
  ]

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back{user?.fullName ? `, ${user.fullName.split(' ')[0]}` : ''}
        </h1>
        <p className="text-gray-500 mt-1">Here's what's happening in your workspace.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
              </div>
              <div className={`${bg} p-3 rounded-lg`}>
                <Icon className={`w-6 h-6 ${color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Projects */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Projects</h2>
          <Link to="/projects" className="text-sm text-blue-600 hover:text-blue-700">View all</Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : recentProjects.length === 0 ? (
          <div className="bg-white rounded-xl p-10 shadow-sm border border-gray-100 text-center">
            <FolderKanban className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 mb-4">No projects yet. Create your first project to get started.</p>
            <Link
              to="/projects"
              className="inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              New Project
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentProjects.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 hover:border-blue-200 hover:shadow-md transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
                  <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full capitalize">
                    {project.task_type?.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-sm text-gray-500 truncate">{project.description || 'No description'}</p>
                <p className="text-xs text-gray-400 mt-3">
                  {new Date(project.created_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
