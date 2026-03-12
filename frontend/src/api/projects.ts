import { coreApi } from './client'

export interface Project {
  id: string
  name: string
  taskType: string
  description: string | null
  orgId: string
  createdAt: string
}

export interface Dataset {
  id: string
  name: string
  imageCount: number
  createdAt: string
}

export const projectsApi = {
  list: (orgId: string) => coreApi.get<Project[]>('/projects', { params: { org_id: orgId } }),
  get: (id: string) => coreApi.get<Project>(`/projects/${id}`),
  create: (data: { name: string; taskType: string; description?: string; orgId: string }) =>
    coreApi.post<Project>('/projects', {
      name: data.name,
      task_type: data.taskType,
      description: data.description,
      org_id: data.orgId,
    }),
  update: (id: string, data: Partial<Project>) => coreApi.put<Project>(`/projects/${id}`, data),
  delete: (id: string) => coreApi.delete(`/projects/${id}`),
}

export const datasetsApi = {
  list: (projectId: string) => coreApi.get<Dataset[]>('/datasets', { params: { project_id: projectId } }),
  get: (id: string) => coreApi.get<Dataset>(`/datasets/${id}`),
  getStats: (id: string) => coreApi.get(`/datasets/${id}/stats`),
  create: (data: { name: string; projectId: string; description?: string }) =>
    coreApi.post<Dataset>('/datasets', { name: data.name, project_id: data.projectId }),
  createVersion: (datasetId: string, data: object) =>
    coreApi.post(`/datasets/${datasetId}/versions`, data),
  listVersions: (datasetId: string) => coreApi.get(`/datasets/${datasetId}/versions`),
}

export const imagesApi = {
  list: (datasetId: string, params?: object) =>
    coreApi.get(`/images/${datasetId}/images`, { params }),
  get: (imageId: string) => coreApi.get(`/images/${imageId}`),
  upload: (datasetId: string, files: File[]) => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return coreApi.post(`/images/${datasetId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  updateSplit: (imageId: string, split: string) =>
    coreApi.patch(`/images/${imageId}/split`, null, { params: { split } }),
  delete: (imageId: string) => coreApi.delete(`/images/${imageId}`),
}

export const annotationsApi = {
  list: (imageId: string) => coreApi.get(`/annotations/images/${imageId}/annotations`),
  create: (imageId: string, data: object) =>
    coreApi.post(`/annotations/images/${imageId}/annotations`, data),
  createBatch: (imageId: string, data: object[]) =>
    coreApi.post(`/annotations/images/${imageId}/annotations/batch`, data),
  update: (annotationId: string, data: object) =>
    coreApi.put(`/annotations/${annotationId}`, data),
  delete: (annotationId: string) => coreApi.delete(`/annotations/${annotationId}`),
  markAnnotated: (imageId: string) =>
    coreApi.post(`/annotations/images/${imageId}/mark-annotated`),
}

export const labelClassesApi = {
  list: (projectId: string) => coreApi.get('/label-classes', { params: { project_id: projectId } }),
  create: (data: object) => coreApi.post('/label-classes', data),
  update: (id: string, data: object) => coreApi.put(`/label-classes/${id}`, data),
  delete: (id: string) => coreApi.delete(`/label-classes/${id}`),
}
