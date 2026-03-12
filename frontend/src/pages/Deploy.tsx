import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Zap, Plus, Activity } from 'lucide-react'
import { inferApi, trainApi } from '../api/client'

export function Deploy() {
  const { projectId } = useParams<{ projectId: string }>()
  const [endpoints, setEndpoints] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', modelVersionId: '' })
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    async function load() {
      const [epRes, mvRes] = await Promise.all([
        inferApi.get('/endpoints', { params: { project_id: projectId } }),
        trainApi.get('/model-versions', { params: { project_id: projectId } }),
      ])
      setEndpoints(epRes.data)
      setModels(mvRes.data.filter((m: any) => m.export_artifacts?.onnx))
    }
    if (projectId) load()
  }, [projectId])

  async function handleCreate() {
    if (!form.name || !form.modelVersionId) return
    setCreating(true)
    try {
      await inferApi.post('/endpoints', {
        project_id: projectId,
        model_version_id: form.modelVersionId,
        name: form.name,
      })
      setShowCreate(false)
      const res = await inferApi.get('/endpoints', { params: { project_id: projectId } })
      setEndpoints(res.data)
    } finally {
      setCreating(false)
    }
  }

  async function toggleStatus(endpoint: any) {
    const newStatus = endpoint.status === 'active' ? 'inactive' : 'active'
    await inferApi.patch(`/endpoints/${endpoint.id}`, { status: newStatus })
    const res = await inferApi.get('/endpoints', { params: { project_id: projectId } })
    setEndpoints(res.data)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Deploy</h1>
          <p className="text-gray-500 mt-1">Manage inference endpoints</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Endpoint
        </button>
      </div>

      {endpoints.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200">
          <Zap className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">No inference endpoints yet.</p>
          <p className="text-sm text-gray-400">
            Deploy a model to create a REST API endpoint for predictions.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {endpoints.map((ep) => (
            <div key={ep.id} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${ep.status === 'active' ? 'bg-green-400' : 'bg-gray-300'}`} />
                  <div>
                    <h3 className="font-medium text-gray-900">{ep.name}</h3>
                    <p className="text-sm text-gray-500 capitalize">{ep.endpoint_type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">{ep.id}</code>
                  <button
                    onClick={() => toggleStatus(ep)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                      ep.status === 'active'
                        ? 'bg-red-50 text-red-600 hover:bg-red-100'
                        : 'bg-green-50 text-green-600 hover:bg-green-100'
                    }`}
                  >
                    {ep.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              </div>

              <div className="mt-3 text-xs text-gray-500 font-mono bg-gray-50 rounded px-3 py-2">
                POST /api/infer/predict/{ep.id}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold mb-4">Create Inference Endpoint</h2>

            {models.length === 0 ? (
              <div className="text-center py-6">
                <p className="text-gray-500 text-sm mb-2">No ONNX-exported models available.</p>
                <p className="text-xs text-gray-400">Export a model to ONNX format first in the Model Registry.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Endpoint Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="production-detector"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Model Version</label>
                  <select
                    value={form.modelVersionId}
                    onChange={(e) => setForm({ ...form, modelVersionId: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Select model...</option>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.architecture})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="flex-1 border border-gray-200 py-2 rounded-lg text-sm">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !form.name || !form.modelVersionId}
                className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Endpoint'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
