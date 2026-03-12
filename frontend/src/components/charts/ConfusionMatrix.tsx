import React from 'react'

interface ConfusionMatrixProps {
  matrix: number[][]
  labels: string[]
  normalize?: boolean
}

export function ConfusionMatrix({ matrix, labels, normalize = false }: ConfusionMatrixProps) {
  const maxVal = normalize ? 1 : Math.max(...matrix.flat())

  const getColor = (value: number, max: number) => {
    const intensity = max > 0 ? value / max : 0
    const r = Math.round(59 + intensity * (239 - 59))
    const g = Math.round(130 + intensity * (68 - 130))
    const b = Math.round(246 + intensity * (68 - 246))
    return `rgb(${r},${g},${b})`
  }

  const displayValue = (value: number) =>
    normalize ? `${(value * 100).toFixed(1)}%` : value.toString()

  return (
    <div className="overflow-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="p-1 text-gray-400 text-right">Pred →</th>
            {labels.map((label) => (
              <th key={label} className="p-1 text-center text-gray-400 max-w-[60px] truncate" title={label}>
                {label.length > 8 ? label.slice(0, 7) + '…' : label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <td className="p-1 text-right text-gray-400 pr-2 max-w-[80px] truncate" title={labels[i]}>
                {labels[i].length > 10 ? labels[i].slice(0, 9) + '…' : labels[i]}
              </td>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className="p-1 text-center font-mono"
                  style={{
                    backgroundColor: getColor(cell, maxVal),
                    color: cell / maxVal > 0.5 ? 'white' : '#1f2937',
                    minWidth: 48,
                  }}
                  title={`${labels[i]} → ${labels[j]}: ${cell}`}
                >
                  {displayValue(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 text-xs text-gray-500">Rows = Actual, Columns = Predicted</div>
    </div>
  )
}
