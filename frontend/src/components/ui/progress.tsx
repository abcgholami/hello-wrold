import React from 'react'
import { cn } from '../../lib/utils'

interface ProgressProps {
  value: number
  max?: number
  className?: string
  barClassName?: string
  showLabel?: boolean
}

export function Progress({ value, max = 100, className, barClassName, showLabel }: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div className={cn('relative h-2 w-full overflow-hidden rounded-full bg-gray-700', className)}>
      <div
        className={cn('h-full rounded-full bg-blue-500 transition-all duration-300', barClassName)}
        style={{ width: `${pct}%` }}
      />
      {showLabel && (
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-white">
          {pct.toFixed(0)}%
        </span>
      )}
    </div>
  )
}
