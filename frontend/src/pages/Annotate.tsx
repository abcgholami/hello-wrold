import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Save, Undo, Redo, Trash2 } from 'lucide-react'
import { coreApi } from '../api/client'
import { useAnnotationStore } from '../store/annotationStore'

const TOOLS = [
  { id: 'select', label: 'Select', key: 'V' },
  { id: 'bbox', label: 'BBox', key: 'B' },
  { id: 'polygon', label: 'Polygon', key: 'P' },
  { id: 'pan', label: 'Pan', key: 'Space' },
] as const

export function Annotate() {
  const { projectId, imageId } = useParams<{ projectId: string; imageId: string }>()
  const navigate = useNavigate()
  const canvasContainerRef = useRef<HTMLDivElement>(null)
  const [currentImage, setCurrentImage] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [imageList, setImageList] = useState<string[]>([])
  const [imageIdx, setImageIdx] = useState(0)

  const {
    activeTool, setActiveTool, annotations, labelClasses, selectedLabelClassId,
    setSelectedLabelClass, setLabelClasses, setAnnotations, setCurrentImage: storeSetImage,
    undo, redo, isDirty, markClean, deleteAnnotation, selectedAnnotationId,
  } = useAnnotationStore()

  // Load image list from first dataset in project
  useEffect(() => {
    async function loadImageList() {
      try {
        const dsRes = await coreApi.get('/datasets', { params: { project_id: projectId } })
        const datasets = dsRes.data
        if (datasets.length > 0) {
          const imgRes = await coreApi.get(`/images/${datasets[0].id}/images`, { params: { per_page: 200 } })
          const ids = (imgRes.data.items || []).map((i: any) => i.id)
          setImageList(ids)
          if (imageId) {
            const idx = ids.indexOf(imageId)
            setImageIdx(idx >= 0 ? idx : 0)
          }
        }

        // Load label classes
        const lcRes = await coreApi.get('/label-classes', { params: { project_id: projectId } })
        setLabelClasses(lcRes.data.map((lc: any) => ({
          id: lc.id, name: lc.name, color: lc.color, parentId: lc.parent_id,
        })))
      } catch (e) {
        console.error('Failed to load image list', e)
      }
    }
    if (projectId) loadImageList()
  }, [projectId])

  // Load image + annotations when imageId changes
  useEffect(() => {
    async function loadImage() {
      if (!imageId) return
      try {
        const [imgRes, annRes] = await Promise.all([
          coreApi.get(`/images/${imageId}`),
          coreApi.get(`/annotations/images/${imageId}/annotations`),
        ])
        setCurrentImage(imgRes.data)
        storeSetImage(imageId)
        setAnnotations(annRes.data.map((a: any) => ({
          id: a.id,
          imageId: a.image_id,
          labelClassId: a.label_class_id,
          annotationType: a.annotation_type,
          bbox: a.bbox ? { x: a.bbox[0], y: a.bbox[1], width: a.bbox[2], height: a.bbox[3] } : undefined,
          segmentation: a.segmentation,
          confidence: a.confidence,
          isAiGenerated: a.is_ai_generated,
          reviewStatus: a.review_status,
        })))
      } catch (e) {
        console.error('Failed to load image', e)
      }
    }
    loadImage()
  }, [imageId])

  // Keyboard shortcuts
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      switch (e.key.toUpperCase()) {
        case 'B': setActiveTool('bbox'); break
        case 'P': setActiveTool('polygon'); break
        case 'V': setActiveTool('select'); break
        case ' ': e.preventDefault(); setActiveTool('pan'); break
        case 'Z': if (e.ctrlKey || e.metaKey) { e.preventDefault(); undo() } break
        case 'Y': if (e.ctrlKey || e.metaKey) { e.preventDefault(); redo() } break
        case 'DELETE': case 'BACKSPACE':
          if (selectedAnnotationId) deleteAnnotation(selectedAnnotationId)
          break
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [selectedAnnotationId])

  async function handleSave() {
    if (!imageId || !isDirty) return
    setSaving(true)
    try {
      // Mark image as annotated
      await coreApi.post(`/annotations/images/${imageId}/mark-annotated`)
      markClean()
    } finally {
      setSaving(false)
    }
  }

  function navigate_image(delta: number) {
    const newIdx = imageIdx + delta
    if (newIdx < 0 || newIdx >= imageList.length) return
    setImageIdx(newIdx)
    navigate(`/projects/${projectId}/annotate/${imageList[newIdx]}`)
  }

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Left panel: tools + classes */}
      <div className="w-48 bg-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-700">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Tools</p>
          <div className="space-y-1">
            {TOOLS.map((tool) => (
              <button
                key={tool.id}
                onClick={() => setActiveTool(tool.id as any)}
                className={`w-full flex items-center justify-between px-3 py-1.5 rounded text-sm ${
                  activeTool === tool.id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700'
                }`}
              >
                <span>{tool.label}</span>
                <span className="text-xs text-gray-500">{tool.key}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="p-3 flex-1">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Labels</p>
          <div className="space-y-1">
            {labelClasses.map((lc) => (
              <button
                key={lc.id}
                onClick={() => setSelectedLabelClass(lc.id)}
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm ${
                  selectedLabelClassId === lc.id
                    ? 'bg-gray-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700'
                }`}
              >
                <div
                  className="w-3 h-3 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: lc.color }}
                />
                <span className="truncate">{lc.name}</span>
              </button>
            ))}
            {labelClasses.length === 0 && (
              <p className="text-xs text-gray-500">No label classes. Add them in project settings.</p>
            )}
          </div>
        </div>
      </div>

      {/* Main canvas area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="h-12 bg-gray-800 border-b border-gray-700 flex items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400 truncate max-w-48">{currentImage?.filename}</span>
            {isDirty && <span className="text-xs text-yellow-400">Unsaved changes</span>}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={undo} className="p-1.5 text-gray-400 hover:text-white">
              <Undo className="w-4 h-4" />
            </button>
            <button onClick={redo} className="p-1.5 text-gray-400 hover:text-white">
              <Redo className="w-4 h-4" />
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !isDirty}
              className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50 hover:bg-blue-700"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        {/* Canvas */}
        <div ref={canvasContainerRef} className="flex-1 flex items-center justify-center bg-gray-950 relative">
          {currentImage ? (
            <div className="relative">
              <img
                src={currentImage.original_url}
                alt={currentImage.filename}
                className="max-w-full max-h-full object-contain"
                style={{ maxHeight: 'calc(100vh - 200px)' }}
              />
              {/* Annotation overlay would go here with react-konva */}
              <div className="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                {annotations.length} annotation{annotations.length !== 1 ? 's' : ''}
              </div>
            </div>
          ) : (
            <div className="text-gray-600 text-sm">Select an image to annotate</div>
          )}
        </div>

        {/* Navigation */}
        <div className="h-12 bg-gray-800 border-t border-gray-700 flex items-center justify-between px-4">
          <button
            onClick={() => navigate_image(-1)}
            disabled={imageIdx <= 0}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>
          <span className="text-sm text-gray-400">
            {imageList.length > 0 ? `${imageIdx + 1} / ${imageList.length}` : ''}
          </span>
          <button
            onClick={() => navigate_image(1)}
            disabled={imageIdx >= imageList.length - 1}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white disabled:opacity-30"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Right panel: annotation list */}
      <div className="w-52 bg-gray-800 p-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Annotations ({annotations.length})
        </p>
        <div className="space-y-1">
          {annotations.map((ann) => {
            const lc = labelClasses.find((l) => l.id === ann.labelClassId)
            return (
              <div
                key={ann.id}
                className="flex items-center gap-2 px-2 py-1.5 rounded text-xs text-gray-300 hover:bg-gray-700"
              >
                <div
                  className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: lc?.color || '#888' }}
                />
                <span className="flex-1 truncate">{lc?.name || 'Unknown'}</span>
                <button
                  onClick={() => deleteAnnotation(ann.id)}
                  className="text-gray-500 hover:text-red-400"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
