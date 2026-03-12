import React from 'react'
import { Handle, Position, NodeProps } from 'reactflow'

export interface WorkflowNodeData {
  label: string
  nodeType: string
  config?: Record<string, unknown>
  status?: 'idle' | 'running' | 'error'
  description?: string
}

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-gray-600',
  running: 'border-green-500 shadow-green-500/30 shadow-lg',
  error: 'border-red-500 shadow-red-500/30 shadow-lg',
}

export function BaseWorkflowNode({
  data,
  selected,
  isConnectable,
  showInput = true,
  showOutput = true,
  accentColor = '#3b82f6',
  icon,
  children,
}: NodeProps<WorkflowNodeData> & {
  showInput?: boolean
  showOutput?: boolean
  accentColor?: string
  icon?: React.ReactNode
  children?: React.ReactNode
}) {
  const statusClass = STATUS_COLORS[data.status ?? 'idle']

  return (
    <div
      className={`
        bg-gray-800 rounded-lg border-2 min-w-[160px] max-w-[240px]
        ${statusClass}
        ${selected ? 'ring-2 ring-blue-400' : ''}
        transition-all duration-150
      `}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-[6px]"
        style={{ backgroundColor: `${accentColor}22`, borderBottom: `1px solid ${accentColor}44` }}
      >
        {icon && <span className="text-base">{icon}</span>}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-white truncate">{data.label}</p>
          <p className="text-[10px] text-gray-400 truncate">{data.nodeType}</p>
        </div>
        {data.status === 'running' && (
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        )}
        {data.status === 'error' && (
          <div className="w-2 h-2 rounded-full bg-red-500" />
        )}
      </div>

      {/* Body */}
      {(data.description || children) && (
        <div className="px-3 py-2 text-[11px] text-gray-400">
          {data.description && <p>{data.description}</p>}
          {children}
        </div>
      )}

      {showInput && (
        <Handle
          type="target"
          position={Position.Left}
          isConnectable={isConnectable}
          style={{ background: accentColor, width: 10, height: 10, border: '2px solid #1f2937' }}
        />
      )}
      {showOutput && (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={isConnectable}
          style={{ background: accentColor, width: 10, height: 10, border: '2px solid #1f2937' }}
        />
      )}
    </div>
  )
}
