import { create } from 'zustand'

export type ToolType = 'select' | 'bbox' | 'polygon' | 'mask' | 'classification' | 'polyline' | 'pan'

export interface BBox {
  x: number
  y: number
  width: number
  height: number
}

export interface Annotation {
  id: string
  imageId: string
  labelClassId: string | null
  annotationType: 'bbox' | 'polygon' | 'mask' | 'classification' | 'polyline'
  bbox?: BBox
  segmentation?: number[][]
  confidence: number
  isAiGenerated: boolean
  reviewStatus: 'pending' | 'approved' | 'rejected'
}

export interface LabelClass {
  id: string
  name: string
  color: string
  parentId: string | null
}

interface AnnotationState {
  currentImageId: string | null
  annotations: Annotation[]
  selectedAnnotationId: string | null
  activeTool: ToolType
  labelClasses: LabelClass[]
  selectedLabelClassId: string | null
  history: Annotation[][]
  historyIndex: number
  zoom: number
  isDirty: boolean

  // Actions
  setCurrentImage: (imageId: string) => void
  setAnnotations: (annotations: Annotation[]) => void
  addAnnotation: (annotation: Annotation) => void
  updateAnnotation: (id: string, updates: Partial<Annotation>) => void
  deleteAnnotation: (id: string) => void
  selectAnnotation: (id: string | null) => void
  setActiveTool: (tool: ToolType) => void
  setLabelClasses: (classes: LabelClass[]) => void
  setSelectedLabelClass: (id: string | null) => void
  setZoom: (zoom: number) => void
  undo: () => void
  redo: () => void
  markClean: () => void
}

export const useAnnotationStore = create<AnnotationState>((set, get) => ({
  currentImageId: null,
  annotations: [],
  selectedAnnotationId: null,
  activeTool: 'bbox',
  labelClasses: [],
  selectedLabelClassId: null,
  history: [[]],
  historyIndex: 0,
  zoom: 1,
  isDirty: false,

  setCurrentImage: (imageId) => set({
    currentImageId: imageId,
    annotations: [],
    selectedAnnotationId: null,
    history: [[]],
    historyIndex: 0,
    isDirty: false,
  }),

  setAnnotations: (annotations) => set({
    annotations,
    history: [annotations],
    historyIndex: 0,
    isDirty: false,
  }),

  addAnnotation: (annotation) => set((state) => {
    const newAnnotations = [...state.annotations, annotation]
    const newHistory = state.history.slice(0, state.historyIndex + 1)
    newHistory.push(newAnnotations)
    return {
      annotations: newAnnotations,
      history: newHistory,
      historyIndex: newHistory.length - 1,
      isDirty: true,
    }
  }),

  updateAnnotation: (id, updates) => set((state) => {
    const newAnnotations = state.annotations.map((ann) =>
      ann.id === id ? { ...ann, ...updates } : ann
    )
    const newHistory = state.history.slice(0, state.historyIndex + 1)
    newHistory.push(newAnnotations)
    return {
      annotations: newAnnotations,
      history: newHistory,
      historyIndex: newHistory.length - 1,
      isDirty: true,
    }
  }),

  deleteAnnotation: (id) => set((state) => {
    const newAnnotations = state.annotations.filter((ann) => ann.id !== id)
    const newHistory = state.history.slice(0, state.historyIndex + 1)
    newHistory.push(newAnnotations)
    return {
      annotations: newAnnotations,
      selectedAnnotationId: state.selectedAnnotationId === id ? null : state.selectedAnnotationId,
      history: newHistory,
      historyIndex: newHistory.length - 1,
      isDirty: true,
    }
  }),

  selectAnnotation: (id) => set({ selectedAnnotationId: id }),

  setActiveTool: (tool) => set({ activeTool: tool, selectedAnnotationId: null }),

  setLabelClasses: (classes) => set({
    labelClasses: classes,
    selectedLabelClassId: classes.length > 0 ? classes[0].id : null,
  }),

  setSelectedLabelClass: (id) => set({ selectedLabelClassId: id }),

  setZoom: (zoom) => set({ zoom: Math.min(10, Math.max(0.1, zoom)) }),

  undo: () => set((state) => {
    if (state.historyIndex <= 0) return state
    const newIndex = state.historyIndex - 1
    return {
      historyIndex: newIndex,
      annotations: state.history[newIndex],
      isDirty: true,
    }
  }),

  redo: () => set((state) => {
    if (state.historyIndex >= state.history.length - 1) return state
    const newIndex = state.historyIndex + 1
    return {
      historyIndex: newIndex,
      annotations: state.history[newIndex],
      isDirty: true,
    }
  }),

  markClean: () => set({ isDirty: false }),
}))
