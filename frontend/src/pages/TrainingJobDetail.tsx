import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, Loader, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { trainApi } from '../api/client'

export function TrainingJobDetail() {
  const { projectId, jobId } = useParams<{ projectId: string; jobId: string }>()
  const [job, setJob] = useState<any>(null)
  const [metrics, setMetrics] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    async function loadJob() {
      const [jobRes, metricsRes] = await Promise.all([
        trainApi.get(`/training-jobs/${jobId}`),
        trainApi.get(`/training-jobs/${jobId}/metrics`),
      ])
      setJob(jobRes.data)
      setMetrics(metricsRes.data.map((m: any) => ({ epoch: m.epoch, ...m.metrics })))
    }
    if (jobId) loadJob()
  }, [jobId])

  // WebSocket for live updates
  useEffect(() => {
    if (!jobId) return
    const wsUrl = `ws://localhost:8001/ws/training/${jobId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'epoch') {
        setMetrics((prev) => [...prev, { epoch: data.epoch, ...data.metrics }])
        setJob((prev: any) => ({
          ...prev,
          current_epoch: data.epoch,
          best_metric: data.best_metric,
        }))
      } else if (data.type === 'status') {
        setJob((prev: any) => ({ ...prev, status: data.status }))
      }
    }

    return () => ws.close()
  }, [jobId])

  if (!job) return <div className="p-8 text-gray-400">Loading...</div>

  const StatusIcon = job.status === 'running' ? Loader
    : job.status === 'completed' ? CheckCircle
    : job.status === 'failed' ? XCircle
    : AlertCircle

  const statusColor = job.status === 'running' ? 'text-blue-500'
    : job.status === 'completed' ? 'text-green-500'
    : 'text-red-500'

  const progress = job.total_epochs > 0 ? (job.current_epoch / job.total_epochs) * 100 : 0

  return (
    <div className="p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to={`/projects/${projectId}/train`} className="hover:text-gray-900">Training Jobs</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-gray-900 font-medium">{job.architecture}</span>
      </div>

      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <StatusIcon className={`w-7 h-7 ${statusColor} ${job.status === 'running' ? 'animate-spin' : ''}`} />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{job.architecture}</h1>
          <p className="text-gray-500">{job.task_type?.replace('_', ' ')} · {job.preset} preset</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stats */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-500 mb-3">Progress</h3>
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-gray-700">Epoch {job.current_epoch} / {job.total_epochs}</span>
              <span className="font-medium">{progress.toFixed(0)}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {job.best_metric && (
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
              <h3 className="text-sm font-semibold text-gray-500 mb-1">Best Metric</h3>
              <p className="text-2xl font-bold text-gray-900">{job.best_metric.toFixed(4)}</p>
              <p className="text-sm text-gray-500">{job.best_metric_name || 'mAP50'}</p>
            </div>
          )}

          {/* Hyperparameters */}
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-semibold text-gray-500 mb-3">Hyperparameters</h3>
            <dl className="space-y-1.5">
              {Object.entries(job.hyperparameters || {}).slice(0, 8).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <dt className="text-gray-500">{k}</dt>
                  <dd className="font-mono text-gray-900">{String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>

          {job.mlflow_run_id && (
            <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
              <p className="text-xs text-gray-500 font-mono">{job.mlflow_run_id}</p>
              <p className="text-xs text-gray-400 mt-1">MLflow Run ID</p>
            </div>
          )}
        </div>

        {/* Charts */}
        <div className="lg:col-span-2 space-y-4">
          {metrics.length > 0 && (
            <>
              {/* Loss curve */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">Training Loss</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={metrics}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="epoch" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="train_loss" name="Train Loss" stroke="#3b82f6" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="val_loss" name="Val Loss" stroke="#ef4444" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* mAP curve */}
              <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700 mb-4">mAP</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={metrics}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="epoch" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} domain={[0, 1]} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="metrics/mAP50(B)" name="mAP50" stroke="#22c55e" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="metrics/mAP50-95(B)" name="mAP50-95" stroke="#a855f7" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}

          {metrics.length === 0 && job.status === 'running' && (
            <div className="bg-white rounded-xl p-10 shadow-sm border border-gray-100 text-center">
              <Loader className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
              <p className="text-gray-500">Waiting for first epoch metrics...</p>
            </div>
          )}

          {job.error_message && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-sm font-medium text-red-700 mb-1">Training Error</p>
              <pre className="text-xs text-red-600 whitespace-pre-wrap">{job.error_message}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
