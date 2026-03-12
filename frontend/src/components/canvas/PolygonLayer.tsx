import React from 'react'
import { Line, Circle, Group } from 'react-konva'
import { Annotation } from '../../store/annotationStore'

interface PolygonLayerProps {
  annotations: Annotation[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  offsetX: number
  offsetY: number
  imgW: number
  imgH: number
}

export function PolygonLayer({
  annotations,
  selectedId,
  onSelect,
  offsetX,
  offsetY,
  imgW,
  imgH,
}: PolygonLayerProps) {
  return (
    <>
      {annotations.map((ann) => {
        const segs = ann.segmentation?.[0]
        if (!segs || segs.length < 4) return null
        const isSelected = ann.id === selectedId
        const color = ann.labelClassColor || '#3b82f6'

        // Convert normalized coords to canvas coords
        const points = segs.flatMap((v, i) =>
          i % 2 === 0 ? [offsetX + v * imgW] : [offsetY + v * imgH]
        )

        return (
          <Group key={ann.id} onClick={() => onSelect(ann.id)}>
            <Line
              points={points}
              closed
              stroke={color}
              strokeWidth={isSelected ? 3 : 2}
              fill={`${color}${isSelected ? '44' : '22'}`}
            />
            {isSelected &&
              segs.reduce((acc: React.ReactNode[], _, i) => {
                if (i % 2 === 0) {
                  acc.push(
                    <Circle
                      key={i}
                      x={offsetX + segs[i] * imgW}
                      y={offsetY + segs[i + 1] * imgH}
                      radius={5}
                      fill={color}
                      stroke="white"
                      strokeWidth={1.5}
                    />
                  )
                }
                return acc
              }, [])}
          </Group>
        )
      })}
    </>
  )
}
