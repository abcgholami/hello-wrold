import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Database, PenTool, Brain, Boxes, Workflow, ChevronRight } from 'lucide-react'
import { coreApi } from '../api/client'

export function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<any>(null)
  const [datasets, setDatasets] = useState<any[]>([])

  useEffect(() => {
    async function fetchData() {
      const [pRes, dRes] = await Promise.all([
        coreApi.get(`/projects/${projectId}`),
        coreApi.get('/datasets', { params: { project_id: projectId } }),
      ])
      setProject(pRes.data)
      setDatasets(dRes.data)
    }
    if (projectId) fetchData()
  }, [projectId])

  if (!project) return (
    <div className="p-8 text-gray-400">Loading...</div>
  )

  const modules = [
    {
      icon: Database,
      label: 'Datasets',
      description: `${datasets.length} dataset${datasets.length !== 1 ? 's' : ''}`,
      color: 'text-purple-500',
      bg: 'bg-purple-50',
      links: datasets.map((d: any) => ({ label: d.name, to: `/projects/${projectId}/datasets/${d.id}` })),
      action: { label: 'Manage Datasets', to: `/projects/${projectId}/datasets` },
    },
    {
      icon: PenTool,
      label: 'Annotate',
      description: 'Label images for training',
      color: 'text-blue-500',
      bg: 'bg-blue-50',
      links: [],
      action: { label: 'Open Annotation Tool', to: `/projects/${projectId}/annotate` },
    },
    {
      icon: Brain,
      label: 'Train',
      description: 'Launch training jobs',
      color: 'text-green-500',
      bg: 'bg-green-50',
      links: [],
      action: { label: 'Training Jobs', to: `/projects/${projectId}/train` },
    },
    {
      icon: Boxes,
      label: 'Model Registry',
      description: 'Manage model versions',
      color: 'text-orange-500',
      bg: 'bg-orange-50',
      links: [],
      action: { label: 'View Models', to: `/projects/${projectId}/registry` },
    },
    {
      icon: Workflow,
      label: 'Deploy',
      description: 'Create inference endpoints',
      color: 'text-teal-500',
      bg: 'bg-teal-50',
      links: [],
      action: { label: 'Manage Endpoints', to: `/projects/${projectId}/deploy` },
    },
  ]

  return (
    <div className="p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/projects" className="hover:text-gray-900">Projects</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-gray-900 font-medium">{project.name}</span>
      </div>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          <span className="text-sm bg-blue-50 text-blue-700 px-2.5 py-0.5 rounded-full capitalize">
            {project.task_type?.replace('_', ' ')}
          </span>
        </div>
        {project.description && <p className="text-gray-500">{project.description}</p>}
      </div>

      {/* Modules */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {modules.map(({ icon: Icon, label, description, color, bg, links, action }) => (
          <div key={label} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <div className="flex items-center gap-3 mb-3">
              <div className={`${bg} p-2.5 rounded-lg`}>
                <Icon className={`w-5 h-5 ${color}`} />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{label}</h3>
                <p className="text-sm text-gray-500">{description}</p>
              </div>
            </div>

            {links.slice(0, 3).map((link: any) => (
              <Link
                key={link.to}
                to={link.to}
                className="block text-sm text-gray-600 hover:text-blue-600 py-1 truncate"
              >
                {link.label}
              </Link>
            ))}

            <Link
              to={action.to}
              className={`mt-3 block text-sm font-medium ${color} hover:underline`}
            >
              {action.label} →
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}
