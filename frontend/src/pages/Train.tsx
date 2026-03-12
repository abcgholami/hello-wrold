import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Plus, Brain, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'
import { trainApi } from '../api/client'
import { coreApi } from '../api/client'

const STATUS_ICONS: Record<string, any> = {
  queued: Clock,
  running: Loader,
  completed: CheckCircle,
  failed: XCircle,
  cancelled: XCircle,
}

const STATUS_COLORS: Record<string, string> = {
  queued: 'text-yellow-500',
  running: 'text-blue-500',
  completed: 'text-green-500',
  failed: 'text-red-500',
  cancelled: 'text-gray-400',
}

export function Train() {
  const { projectId } = useParams<{ projectId: string }>()
  const [jobs, setJobs] = useState<any[]>([])
  const [showWizard, setShowWizard] = useState(false)
  const [architectures, setArchitectures] = useState<Record<string, string[]>>({})
  const [presets, setPresets] = useState<Record<string, any>>({})
  const [datasetVersions, setDatasetVersions] = useState<any[]>([])
  const [form, setForm] = useState({
    taskType: 'detection',
    architecture: 'yolov8n',
    datasetVersionId: '',
    preset: 'balanced',
  })
  const [launching, setLaunching] = useState(false)

  useEffect(() => {
    async function load() {
      const [jobsRes, archRes, presetsRes] = await Promise.all([
        trainApi.get('/training-jobs', { params: { project_id: projectId } }),
        trainApi.get('/training-jobs/architectures/list'),
        trainApi.get('/training-jobs/presets/list'),
      ])
      setJobs(jobsRes.data)
      setArchitectures(archRes.data)
      setPresets(presetsRes.data)

      // Load dataset versions
      const dsRes = await coreApi.get('/datasets', { params: { project_id: projectId } })
      const versions: any[] = []
      for (const ds of dsRes.data.slice(0, 3)) {
        const vRes = await coreApi.get(`/datasets/${ds.id}/versions`)
        versions.push(...vRes.data.map((v: any) => ({ ...v, datasetName: ds.name })))
      }
      setDatasetVersions(versions)
    }
    if (projectId) load()
  }, [projectId])

  const availableArchitectures = architectures[form.taskType] || []

  async function handleLaunch() {
    if (!form.datasetVersionId) return
    setLaunching(true)
    try {
      await trainApi.post('/training-jobs', {
        project_id: projectId,
        dataset_version_id: form.datasetVersionId,
        task_type: form.taskType,
        architecture: form.architecture,
        preset: form.preset,
      })
      setShowWizard(false)
      const res = await trainApi.get('/training-jobs', { params: { project_id: projectId } })
      setJobs(res.data)
    } finally {
      setLaunching(false)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Training Jobs</h1>
          <p className="text-gray-500 mt-1">Launch and monitor model training</p>
        </div>
        <button
          onClick={() => setShowWizard(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Launch Training
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200">
          <Brain className="w-16 h-16 text-gray-200 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">No training jobs yet. Launch your first training run.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const Icon = STATUS_ICONS[job.status] || Clock
            const color = STATUS_COLORS[job.status] || 'text-gray-500'
            const progress = job.total_epochs > 0 ? (job.current_epoch / job.total_epochs) * 100 : 0

            return (
              <Link
                key={job.id}
                to={`/projects/${projectId}/train/${job.id}`}
                className="block bg-white rounded-xl p-4 shadow-sm border border-gray-100 hover:border-blue-200"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Icon className={`w-5 h-5 ${color} ${job.status === 'running' ? 'animate-spin' : ''}`} />
                    <div>
                      <p className="font-medium text-gray-900">{job.architecture}</p>
                      <p className="text-sm text-gray-500 capitalize">{job.task_type?.replace('_', ' ')}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium capitalize text-gray-700">{job.status}</p>
                    {job.best_metric && (
                      <p className="text-sm text-gray-500">
                        {job.best_metric_name}: {job.best_metric.toFixed(3)}
                      </p>
                    )}
                  </div>
                </div>

                {job.status === 'running' && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>Epoch {job.current_epoch}/{job.total_epochs}</span>
                      <span>{progress.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                )}
              </Link>
            )
          })}
        </div>
      )}

      {/* Launch wizard modal */}
      {showWizard && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Launch Training Job</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Task Type</label>
                <select
                  value={form.taskType}
                  onChange={(e) => {
                    const tt = e.target.value
                    setForm({ ...form, taskType: tt, architecture: (architectures[tt] || [])[0] || '' })
                  }}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Object.keys(architectures).map((t) => (
                    <option key={t} value={t}>{t.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Architecture</label>
                <select
                  value={form.architecture}
                  onChange={(e) => setForm({ ...form, architecture: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {availableArchitectures.map((arch) => (
                    <option key={arch} value={arch}>{arch}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Dataset Version</label>
                <select
                  value={form.datasetVersionId}
                  onChange={(e) => setForm({ ...form, datasetVersionId: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select a dataset version...</option>
                  {datasetVersions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.datasetName} — {v.name} ({v.image_count} images)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Training Preset</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(presets).map(([name, config]: any) => (
                    <button
                      key={name}
                      type="button"
                      onClick={() => setForm({ ...form, preset: name })}
                      className={`p-3 rounded-lg border text-left transition-colors ${
                        form.preset === name
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <p className="text-sm font-medium capitalize">{name}</p>
                      <p className="text-xs text-gray-500 mt-1">{config.epochs} epochs</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowWizard(false)}
                className="flex-1 border border-gray-200 text-gray-700 py-2 rounded-lg text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleLaunch}
                disabled={launching || !form.datasetVersionId}
                className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {launching ? 'Launching...' : 'Launch Training'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
