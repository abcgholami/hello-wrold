import { trainApi } from './client'

export const trainingApi = {
  createJob: (data: object) => trainApi.post('/training-jobs', data),
  listJobs: (projectId: string) => trainApi.get('/training-jobs', { params: { project_id: projectId } }),
  getJob: (jobId: string) => trainApi.get(`/training-jobs/${jobId}`),
  getMetrics: (jobId: string) => trainApi.get(`/training-jobs/${jobId}/metrics`),
  cancelJob: (jobId: string) => trainApi.post(`/training-jobs/${jobId}/cancel`),
  listArchitectures: () => trainApi.get('/training-jobs/architectures/list'),
  listPresets: () => trainApi.get('/training-jobs/presets/list'),

  listModelVersions: (projectId: string) =>
    trainApi.get('/model-versions', { params: { project_id: projectId } }),
  getModelVersion: (versionId: string) => trainApi.get(`/model-versions/${versionId}`),
  promoteModel: (versionId: string, stage: string) =>
    trainApi.post(`/model-versions/${versionId}/promote`, { stage }),
  exportModel: (versionId: string, format: string, quantization?: string) =>
    trainApi.post(`/model-versions/${versionId}/export`, { format, quantization }),
  deleteModelVersion: (versionId: string) => trainApi.delete(`/model-versions/${versionId}`),
}
