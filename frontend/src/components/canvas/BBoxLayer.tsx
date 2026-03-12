import React from 'react'
import { Rect, Group, Text } from 'react-konva'
import { Annotation } from '../../store/annotationStore'

interface BBoxLayerProps {
  annotations: Annotation[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  onUpdate: (id: string, patch: Partial<Annotation>) => void
  offsetX: number
  offsetY: number
  imgW: number
  imgH: number
  readOnly?: boolean
}

export function BBoxLayer({
  annotations,
  selectedId,
  onSelect,
  onUpdate,
  offsetX,
  offsetY,
  imgW,
  imgH,
  readOnly = false,
}: BBoxLayerProps) {
  return (
    <>
      {annotations.map((ann) => {
        if (!ann.bbox) return null
        const [nx, ny, nw, nh] = ann.bbox
        const x = offsetX + nx * imgW
        const y = offsetY + ny * imgH
        const w = nw * imgW
        const h = nh * imgH
        const isSelected = ann.id === selectedId
        const color = ann.labelClassColor || '#ef4444'

        return (
          <Group key={ann.id}>
            <Rect
              x={x}
              y={y}
              width={w}
              height={h}
              stroke={color}
              strokeWidth={isSelected ? 3 : 2}
              fill={`${color}${isSelected ? '33' : '1a'}`}
              draggable={!readOnly && isSelected}
              onClick={() => onSelect(ann.id)}
              onDragEnd={(e) => {
                if (readOnly) return
                const newX = (e.target.x() - offsetX) / imgW
                const newY = (e.target.y() - offsetY) / imgH
                onUpdate(ann.id, { bbox: [newX, newY, nw, nh] })
                e.target.x(x)
                e.target.y(y)
              }}
            />
            {/* Label chip */}
            <Rect
              x={x}
              y={y - 18}
              width={Math.min(ann.labelClassName.length * 7 + 8, w)}
              height={18}
              fill={color}
              cornerRadius={2}
            />
            <Text
              x={x + 4}
              y={y - 16}
              text={ann.labelClassName}
              fontSize={11}
              fill="white"
              fontStyle="bold"
            />
          </Group>
        )
      })}
    </>
  )
}
