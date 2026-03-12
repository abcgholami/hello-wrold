import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

interface MetricPoint {
  epoch: number
  [key: string]: number
}

interface TrainingChartProps {
  data: MetricPoint[]
  metrics?: string[]
  title?: string
  height?: number
}

const METRIC_COLORS: Record<string, string> = {
  loss: '#ef4444',
  val_loss: '#f97316',
  mAP50: '#22c55e',
  'mAP50-95': '#14b8a6',
  top1_acc: '#3b82f6',
  top5_acc: '#8b5cf6',
  precision: '#06b6d4',
  recall: '#84cc16',
}

const DEFAULT_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f97316', '#8b5cf6', '#14b8a6',
]

export function TrainingChart({ data, metrics, title, height = 300 }: TrainingChartProps) {
  const detectedMetrics = metrics ?? (data.length > 0
    ? Object.keys(data[0]).filter((k) => k !== 'epoch')
    : [])

  return (
    <div>
      {title && <h3 className="text-sm font-medium text-gray-400 mb-2">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="epoch"
            stroke="#9ca3af"
            tick={{ fontSize: 11 }}
            label={{ value: 'Epoch', position: 'insideBottom', offset: -3, fill: '#9ca3af', fontSize: 11 }}
          />
          <YAxis stroke="#9ca3af" tick={{ fontSize: 11 }} width={40} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
            labelStyle={{ color: '#f9fafb' }}
            itemStyle={{ fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af' }} />
          {detectedMetrics.map((metric, i) => (
            <Line
              key={metric}
              type="monotone"
              dataKey={metric}
              stroke={METRIC_COLORS[metric] ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
