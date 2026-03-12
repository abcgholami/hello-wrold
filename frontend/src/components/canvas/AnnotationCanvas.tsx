import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Rect, Line, Circle, Group, Text } from 'react-konva'
import useImage from 'use-image'
import { useAnnotationStore, Tool, Annotation } from '../../store/annotationStore'
import { BBoxLayer } from './BBoxLayer'
import { PolygonLayer } from './PolygonLayer'

interface AnnotationCanvasProps {
  imageUrl: string
  imageId: string
  width: number
  height: number
  readOnly?: boolean
}

export function AnnotationCanvas({ imageUrl, imageId, width, height, readOnly = false }: AnnotationCanvasProps) {
  const {
    tool,
    annotations,
    selectedAnnotationId,
    currentLabelClass,
    addAnnotation,
    updateAnnotation,
    selectAnnotation,
  } = useAnnotationStore()

  const [image] = useImage(imageUrl, 'anonymous')
  const stageRef = useRef<any>(null)

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null)
  const [currentRect, setCurrentRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [polygonPoints, setPolygonPoints] = useState<number[]>([])

  // Scale image to fit canvas
  const scale = image
    ? Math.min(width / image.naturalWidth, height / image.naturalHeight)
    : 1
  const imgW = image ? image.naturalWidth * scale : width
  const imgH = image ? image.naturalHeight * scale : height
  const offsetX = (width - imgW) / 2
  const offsetY = (height - imgH) / 2

  const getRelativePos = (e: any) => {
    const pos = e.target.getStage().getPointerPosition()
    return {
      x: (pos.x - offsetX) / imgW,
      y: (pos.y - offsetY) / imgH,
    }
  }

  const handleMouseDown = useCallback(
    (e: any) => {
      if (readOnly) return
      if (tool === Tool.SELECT) return
      const pos = getRelativePos(e)

      if (tool === Tool.BBOX) {
        setIsDrawing(true)
        setDrawStart(pos)
        setCurrentRect({ x: pos.x, y: pos.y, w: 0, h: 0 })
      } else if (tool === Tool.POLYGON) {
        setPolygonPoints((prev) => [...prev, pos.x, pos.y])
      }
    },
    [tool, readOnly, offsetX, offsetY, imgW, imgH]
  )

  const handleMouseMove = useCallback(
    (e: any) => {
      if (!isDrawing || tool !== Tool.BBOX || !drawStart) return
      const pos = getRelativePos(e)
      setCurrentRect({
        x: Math.min(drawStart.x, pos.x),
        y: Math.min(drawStart.y, pos.y),
        w: Math.abs(pos.x - drawStart.x),
        h: Math.abs(pos.y - drawStart.y),
      })
    },
    [isDrawing, tool, drawStart, offsetX, offsetY, imgW, imgH]
  )

  const handleMouseUp = useCallback(
    (e: any) => {
      if (!isDrawing || tool !== Tool.BBOX || !currentRect) return
      if (currentRect.w > 0.01 && currentRect.h > 0.01) {
        addAnnotation({
          imageId,
          labelClassId: currentLabelClass?.id ?? '',
          labelClassName: currentLabelClass?.name ?? 'Unknown',
          labelClassColor: currentLabelClass?.color ?? '#ef4444',
          type: 'bbox',
          bbox: [currentRect.x, currentRect.y, currentRect.w, currentRect.h],
        })
      }
      setIsDrawing(false)
      setDrawStart(null)
      setCurrentRect(null)
    },
    [isDrawing, tool, currentRect, imageId, currentLabelClass, addAnnotation]
  )

  const handleDblClick = useCallback(() => {
    if (tool !== Tool.POLYGON || polygonPoints.length < 6) return
    addAnnotation({
      imageId,
      labelClassId: currentLabelClass?.id ?? '',
      labelClassName: currentLabelClass?.name ?? 'Unknown',
      labelClassColor: currentLabelClass?.color ?? '#ef4444',
      type: 'polygon',
      segmentation: [polygonPoints],
    })
    setPolygonPoints([])
  }, [tool, polygonPoints, imageId, currentLabelClass, addAnnotation])

  const handleStageClick = useCallback(
    (e: any) => {
      if (e.target === e.target.getStage()) {
        selectAnnotation(null)
      }
    },
    [selectAnnotation]
  )

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDblClick={handleDblClick}
      onClick={handleStageClick}
      style={{ cursor: tool === Tool.SELECT ? 'default' : 'crosshair' }}
    >
      {/* Background */}
      <Layer>
        <Rect x={0} y={0} width={width} height={height} fill="#1a1a2e" />
        {image && (
          <KonvaImage
            image={image}
            x={offsetX}
            y={offsetY}
            width={imgW}
            height={imgH}
          />
        )}
      </Layer>

      {/* Existing annotations */}
      <Layer>
        <BBoxLayer
          annotations={annotations.filter((a) => a.type === 'bbox')}
          selectedId={selectedAnnotationId}
          onSelect={selectAnnotation}
          onUpdate={updateAnnotation}
          offsetX={offsetX}
          offsetY={offsetY}
          imgW={imgW}
          imgH={imgH}
          readOnly={readOnly}
        />
        <PolygonLayer
          annotations={annotations.filter((a) => a.type === 'polygon')}
          selectedId={selectedAnnotationId}
          onSelect={selectAnnotation}
          offsetX={offsetX}
          offsetY={offsetY}
          imgW={imgW}
          imgH={imgH}
        />
      </Layer>

      {/* In-progress drawing */}
      <Layer>
        {tool === Tool.BBOX && currentRect && (
          <Rect
            x={offsetX + currentRect.x * imgW}
            y={offsetY + currentRect.y * imgH}
            width={currentRect.w * imgW}
            height={currentRect.h * imgH}
            stroke={currentLabelClass?.color ?? '#ef4444'}
            strokeWidth={2}
            dash={[4, 4]}
            fill={`${currentLabelClass?.color ?? '#ef4444'}22`}
          />
        )}
        {tool === Tool.POLYGON && polygonPoints.length >= 2 && (
          <>
            <Line
              points={polygonPoints.flatMap((v, i) =>
                i % 2 === 0 ? [offsetX + v * imgW] : [offsetY + v * imgH]
              )}
              stroke={currentLabelClass?.color ?? '#ef4444'}
              strokeWidth={2}
              closed={false}
            />
            {polygonPoints.reduce((acc: React.ReactNode[], _, i) => {
              if (i % 2 === 0) {
                acc.push(
                  <Circle
                    key={i}
                    x={offsetX + polygonPoints[i] * imgW}
                    y={offsetY + polygonPoints[i + 1] * imgH}
                    radius={4}
                    fill={currentLabelClass?.color ?? '#ef4444'}
                  />
                )
              }
              return acc
            }, [])}
          </>
        )}
      </Layer>
    </Stage>
  )
}
