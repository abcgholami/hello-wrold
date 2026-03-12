import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Boxes, Download, TrendingUp } from 'lucide-react'
import { trainApi } from '../api/client'

const STAGE_COLORS: Record<string, string> = {
  development: 'bg-gray-100 text-gray-700',
  staging: 'bg-yellow-100 text-yellow-700',
  production: 'bg-green-100 text-green-700',
  archived: 'bg-red-100 text-red-700',
}

export function ModelRegistry() {
  const { projectId } = useParams<{ projectId: string }>()
  const [versions, setVersions] = useState<any[]>([])
  const [exporting, setExporting] = useState<Record<string, boolean>>({})

  useEffect(() => {
    async function load() {
      const res = await trainApi.get('/model-versions', { params: { project_id: projectId } })
      setVersions(res.data)
    }
    if (projectId) load()
  }, [projectId])

  async function handlePromote(versionId: string, stage: string) {
    await trainApi.post(`/model-versions/${versionId}/promote`, { stage })
    const res = await trainApi.get('/model-versions', { params: { project_id: projectId } })
    setVersions(res.data)
  }

  async function handleExport(versionId: string, format: string) {
    setExporting((prev) => ({ ...prev, [versionId]: true }))
    try {
      await trainApi.post(`/model-versions/${versionId}/export`, { format })
    } finally {
      setExporting((prev) => ({ ...prev, [versionId]: false }))
    }
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Model Registry</h1>
        <p className="text-gray-500 mt-1">{versions.length} model version{versions.length !== 1 ? 's' : ''}</p>
      </div>

      {versions.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200">
          <Boxes className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <p className="text-gray-500">No model versions yet. Complete a training job first.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {versions.map((v) => (
            <div key={v.id} className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-semibold text-gray-900">{v.name || `v${v.version_number}`}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STAGE_COLORS[v.stage]}`}>
                      {v.stage}
                    </span>
                    {v.is_champion && (
                      <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full">
                        Champion
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">
                    {v.architecture} · {v.task_type?.replace('_', ' ')}
                  </p>
                  {v.metrics && (
                    <div className="flex items-center gap-3 mt-2">
                      <TrendingUp className="w-4 h-4 text-gray-400" />
                      {Object.entries(v.metrics).map(([k, val]) => (
                        <span key={k} className="text-xs text-gray-600">
                          <span className="font-medium">{k}:</span> {(val as number).toFixed(3)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {/* Export */}
                  <button
                    onClick={() => handleExport(v.id, 'onnx')}
                    disabled={exporting[v.id]}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    {exporting[v.id] ? 'Exporting...' : 'ONNX'}
                  </button>

                  {/* Promote */}
                  {v.stage === 'development' && (
                    <button
                      onClick={() => handlePromote(v.id, 'staging')}
                      className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-xs font-medium hover:bg-yellow-200"
                    >
                      → Staging
                    </button>
                  )}
                  {v.stage === 'staging' && (
                    <button
                      onClick={() => handlePromote(v.id, 'production')}
                      className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200"
                    >
                      → Production
                    </button>
                  )}
                  {v.stage === 'production' && (
                    <button
                      onClick={() => handlePromote(v.id, 'archived')}
                      className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200"
                    >
                      Archive
                    </button>
                  )}
                </div>
              </div>

              {/* Export artifacts */}
              {v.export_artifacts && Object.keys(v.export_artifacts).length > 0 && (
                <div className="mt-3 flex gap-2 flex-wrap">
                  {Object.keys(v.export_artifacts).map((fmt) => (
                    <span key={fmt} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full uppercase">
                      {fmt}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
