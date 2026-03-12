import React from 'react'

interface PaletteItem {
  type: string
  label: string
  icon: string
  category: 'input' | 'vision' | 'logic' | 'output'
  description: string
}

const PALETTE_ITEMS: PaletteItem[] = [
  // Input
  { type: 'CameraCapture', label: 'Camera', icon: '📷', category: 'input', description: 'Webcam device' },
  { type: 'RTSPStream', label: 'RTSP Stream', icon: '📡', category: 'input', description: 'IP camera / RTSP URL' },
  { type: 'VideoFile', label: 'Video File', icon: '🎥', category: 'input', description: 'Local video file' },
  // Vision
  { type: 'DetectObjects', label: 'Detect', icon: '🔍', category: 'vision', description: 'Object detection' },
  { type: 'ClassifyImage', label: 'Classify', icon: '🏷️', category: 'vision', description: 'Image classification' },
  { type: 'TrackObjects', label: 'Track', icon: '🎯', category: 'vision', description: 'Multi-object tracking' },
  { type: 'CountObjects', label: 'Count', icon: '🔢', category: 'vision', description: 'Count crossings' },
  { type: 'DrawAnnotations', label: 'Draw', icon: '🎨', category: 'vision', description: 'Render annotations' },
  // Logic
  { type: 'FilterByClass', label: 'Filter Class', icon: '🔽', category: 'logic', description: 'Filter by class name' },
  { type: 'Conditional', label: 'Conditional', icon: '⚡', category: 'logic', description: 'If/else branching' },
  { type: 'Throttle', label: 'Throttle', icon: '⏱️', category: 'logic', description: 'Rate limit output' },
  // Output
  { type: 'LiveDashboard', label: 'Dashboard', icon: '📊', category: 'output', description: 'Live browser view' },
  { type: 'SaveToDB', label: 'Save DB', icon: '💾', category: 'output', description: 'Persist events' },
  { type: 'TriggerAlert', label: 'Alert', icon: '🚨', category: 'output', description: 'Webhook notification' },
  { type: 'ExportCSV', label: 'Export CSV', icon: '📄', category: 'output', description: 'Append to CSV file' },
  { type: 'RobotOutput', label: 'Robot', icon: '🤖', category: 'output', description: 'TCP/UDP socket output' },
]

const CATEGORY_COLORS: Record<string, string> = {
  input: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/30',
  vision: 'text-green-400 bg-green-400/10 border-green-400/30',
  logic: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  output: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
}

const CATEGORY_LABELS: Record<string, string> = {
  input: 'Input Sources',
  vision: 'Vision Processing',
  logic: 'Logic & Control',
  output: 'Outputs',
}

interface NodePaletteProps {
  onDragStart?: (nodeType: string, label: string) => void
}

export function NodePalette({ onDragStart }: NodePaletteProps) {
  const categories = ['input', 'vision', 'logic', 'output'] as const

  const handleDragStart = (e: React.DragEvent, item: PaletteItem) => {
    e.dataTransfer.setData('application/reactflow', JSON.stringify({ type: item.type, label: item.label }))
    e.dataTransfer.effectAllowed = 'move'
    onDragStart?.(item.type, item.label)
  }

  return (
    <div className="w-56 bg-gray-900 border-r border-gray-700 overflow-y-auto flex-shrink-0 p-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Node Palette</p>
      {categories.map((cat) => (
        <div key={cat} className="mb-4">
          <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-wider mb-2">
            {CATEGORY_LABELS[cat]}
          </p>
          <div className="space-y-1">
            {PALETTE_ITEMS.filter((item) => item.category === cat).map((item) => (
              <div
                key={item.type}
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                className={`
                  flex items-center gap-2 px-2 py-1.5 rounded border cursor-grab active:cursor-grabbing
                  ${CATEGORY_COLORS[cat]} hover:opacity-80 transition-opacity select-none
                `}
                title={item.description}
              >
                <span className="text-sm">{item.icon}</span>
                <span className="text-xs font-medium flex-1">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
