import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ChevronRight, Save, Play, StopCircle } from 'lucide-react'
import { coreApi } from '../api/client'

// Workflow editor using ReactFlow
// In production: import ReactFlow and build the full node-based editor.
// Here we provide a functional skeleton.

export function WorkflowEditorPage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const [workflow, setWorkflow] = useState<any>(null)
  const [status, setStatus] = useState<string>('stopped')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      const res = await coreApi.get(`/workflows/${workflowId}`)
      setWorkflow(res.data)
      setStatus(res.data.status)
    }
    if (workflowId) load()
  }, [workflowId])

  async function handleSave() {
    if (!workflow) return
    setSaving(true)
    try {
      await coreApi.put(`/workflows/${workflowId}`, { graph: workflow.graph, name: workflow.name })
    } finally {
      setSaving(false)
    }
  }

  async function handleStart() {
    await coreApi.post(`/workflows/${workflowId}/start`)
    setStatus('running')
  }

  async function handleStop() {
    await coreApi.post(`/workflows/${workflowId}/stop`)
    setStatus('stopped')
  }

  if (!workflow) return <div className="p-8 text-gray-400">Loading...</div>

  return (
    <div className="flex flex-col h-screen">
      {/* Toolbar */}
      <div className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Link to="/workflows" className="hover:text-gray-900">Workflows</Link>
          <ChevronRight className="w-4 h-4" />
          <span className="text-gray-900 font-medium">{workflow.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save'}
          </button>
          {status === 'running' ? (
            <button
              onClick={handleStop}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-sm hover:bg-red-100"
            >
              <StopCircle className="w-4 h-4" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleStart}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700"
            >
              <Play className="w-4 h-4" />
              Run
            </button>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 bg-gray-50 relative">
        <div className="absolute inset-0 flex items-center justify-center text-gray-300">
          <div className="text-center">
            <div className="w-48 h-48 border-2 border-dashed border-gray-200 rounded-xl flex items-center justify-center mx-auto mb-4">
              <span className="text-sm text-gray-300">ReactFlow Canvas</span>
            </div>
            <p className="text-sm text-gray-400">Workflow editor — drag nodes from palette to build pipeline</p>
          </div>
        </div>

        {/* Node palette (left sidebar) */}
        <div className="absolute left-0 top-0 bottom-0 w-48 bg-white border-r border-gray-200 p-3">
          <p className="text-xs font-semibold text-gray-400 uppercase mb-3">Node Types</p>
          {[
            { category: 'Input', nodes: ['Camera', 'Video File', 'Image Folder'] },
            { category: 'Model', nodes: ['Detect Objects', 'Classify', 'Segment'] },
            { category: 'Logic', nodes: ['Count Objects', 'Filter By Class', 'Alert Threshold', 'Line Crossing'] },
            { category: 'Output', nodes: ['Save to DB', 'Webhook', 'Export CSV', 'Send Alert'] },
          ].map(({ category, nodes }) => (
            <div key={category} className="mb-4">
              <p className="text-xs text-gray-400 mb-1.5">{category}</p>
              {nodes.map((node) => (
                <div
                  key={node}
                  className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded px-2 py-1.5 mb-1 cursor-grab hover:bg-blue-50 hover:border-blue-200"
                  draggable
                >
                  {node}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
