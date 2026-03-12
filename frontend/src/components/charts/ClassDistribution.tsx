import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { generateColor } from '../../lib/utils'

interface ClassDistributionProps {
  data: Array<{ name: string; count: number }>
  height?: number
  title?: string
}

export function ClassDistribution({ data, height = 200, title }: ClassDistributionProps) {
  const sorted = [...data].sort((a, b) => b.count - a.count)

  return (
    <div>
      {title && <h3 className="text-sm font-medium text-gray-400 mb-2">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={sorted} margin={{ top: 5, right: 10, left: 0, bottom: 30 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="name"
            stroke="#9ca3af"
            tick={{ fontSize: 10, fill: '#9ca3af' }}
            angle={-35}
            textAnchor="end"
          />
          <YAxis stroke="#9ca3af" tick={{ fontSize: 11 }} width={40} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
            labelStyle={{ color: '#f9fafb' }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {sorted.map((_, index) => (
              <Cell key={index} fill={generateColor(index)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
