import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Workflow, Play, StopCircle } from 'lucide-react'
import { coreApi } from '../api/client'

export function Workflows() {
  const [workflows, setWorkflows] = useState<any[]>([])
  const [projects, setProjects] = useState<any[]>([])

  useEffect(() => {
    async function load() {
      const pRes = await coreApi.get('/projects', { params: { org_id: 'default' } })
      setProjects(pRes.data)
      const wfs: any[] = []
      for (const project of pRes.data.slice(0, 5)) {
        const wRes = await coreApi.get('/workflows', { params: { project_id: project.id } })
        wfs.push(...wRes.data.map((w: any) => ({ ...w, projectName: project.name })))
      }
      setWorkflows(wfs)
    }
    load()
  }, [])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="text-gray-500 mt-1">No-code vision pipelines</p>
        </div>
      </div>

      {workflows.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200">
          <Workflow className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-700 mb-2">No workflows yet</h3>
          <p className="text-gray-400 mb-6 max-w-sm mx-auto">
            Build no-code vision pipelines: connect cameras to detection models, count objects, trigger alerts.
          </p>
          <p className="text-sm text-gray-400">
            Create workflows from within a project.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => (
            <div key={wf.id} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${wf.status === 'running' ? 'bg-green-400 animate-pulse' : 'bg-gray-300'}`} />
                  <div>
                    <h3 className="font-medium text-gray-900">{wf.name}</h3>
                    <p className="text-sm text-gray-400">{wf.projectName}</p>
                  </div>
                </div>
                <Link
                  to={`/workflows/${wf.id}/edit`}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  Open Editor →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
