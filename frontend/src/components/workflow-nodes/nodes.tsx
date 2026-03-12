import React from 'react'
import { NodeProps } from 'reactflow'
import { BaseWorkflowNode, WorkflowNodeData } from './BaseWorkflowNode'

// Input nodes
export function CameraNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showInput={false} accentColor="#06b6d4" icon="📷">
    <p className="text-gray-500">Device: {String(props.data.config?.device_index ?? 0)}</p>
  </BaseWorkflowNode>
}

export function RTSPNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showInput={false} accentColor="#06b6d4" icon="📡">
    <p className="text-gray-500 truncate" title={String(props.data.config?.url ?? '')}>
      {String(props.data.config?.url ?? 'rtsp://...')}
    </p>
  </BaseWorkflowNode>
}

export function VideoFileNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showInput={false} accentColor="#06b6d4" icon="🎥">
    <p className="text-gray-500 truncate" title={String(props.data.config?.path ?? '')}>
      {String(props.data.config?.path ?? 'video.mp4')}
    </p>
  </BaseWorkflowNode>
}

// Vision nodes
export function DetectNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#22c55e" icon="🔍">
    <p className="text-gray-500 truncate">conf: {String(props.data.config?.conf_threshold ?? 0.25)}</p>
  </BaseWorkflowNode>
}

export function ClassifyNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#22c55e" icon="🏷️">
    <p className="text-gray-500">top-{String(props.data.config?.top_k ?? 3)}</p>
  </BaseWorkflowNode>
}

export function TrackNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#84cc16" icon="🎯" />
}

export function CountNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#eab308" icon="🔢">
    <p className="text-gray-500">classes: {(props.data.config?.class_filter as string[] | undefined)?.join(', ') || 'all'}</p>
  </BaseWorkflowNode>
}

export function DrawNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#8b5cf6" icon="🎨" />
}

// Logic nodes
export function FilterClassNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#f97316" icon="🔽">
    <p className="text-gray-500">{(props.data.config?.classes as string[] | undefined)?.join(', ')}</p>
  </BaseWorkflowNode>
}

export function ConditionalNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#f59e0b" icon="⚡">
    <p className="text-gray-500">
      {String(props.data.config?.condition_field ?? 'count')} {String(props.data.config?.operator ?? 'gt')} {String(props.data.config?.value ?? 0)}
    </p>
  </BaseWorkflowNode>
}

export function ThrottleNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} accentColor="#6b7280" icon="⏱️">
    <p className="text-gray-500">{String(props.data.config?.rate ?? 1)} fps</p>
  </BaseWorkflowNode>
}

// Output nodes
export function DashboardNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showOutput={false} accentColor="#3b82f6" icon="📊" />
}

export function SaveDBNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showOutput={false} accentColor="#3b82f6" icon="💾" />
}

export function AlertNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showOutput={false} accentColor="#ef4444" icon="🚨">
    <p className="text-gray-500 truncate" title={String(props.data.config?.webhook_url ?? '')}>
      {props.data.config?.webhook_url ? 'webhook configured' : 'no webhook'}
    </p>
  </BaseWorkflowNode>
}

export function ExportCSVNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showOutput={false} accentColor="#10b981" icon="📄" />
}

export function RobotNode(props: NodeProps<WorkflowNodeData>) {
  return <BaseWorkflowNode {...props} showOutput={false} accentColor="#a855f7" icon="🤖">
    <p className="text-gray-500">{String(props.data.config?.protocol ?? 'tcp')}://{String(props.data.config?.host ?? 'robot')}:{String(props.data.config?.port ?? 5555)}</p>
  </BaseWorkflowNode>
}

// Node type registry for ReactFlow
export const nodeTypes = {
  CameraCapture: CameraNode,
  RTSPStream: RTSPNode,
  VideoFile: VideoFileNode,
  DetectObjects: DetectNode,
  ClassifyImage: ClassifyNode,
  TrackObjects: TrackNode,
  CountObjects: CountNode,
  DrawAnnotations: DrawNode,
  FilterByClass: FilterClassNode,
  Conditional: ConditionalNode,
  Throttle: ThrottleNode,
  LiveDashboard: DashboardNode,
  SaveToDB: SaveDBNode,
  TriggerAlert: AlertNode,
  ExportCSV: ExportCSVNode,
  RobotOutput: RobotNode,
}
