import { useEffect, useState, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, Upload, Grid, List, Filter } from 'lucide-react'
import { coreApi } from '../api/client'

export function DatasetDetail() {
  const { projectId, datasetId } = useParams<{ projectId: string; datasetId: string }>()
  const [dataset, setDataset] = useState<any>(null)
  const [images, setImages] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [dsRes, imgRes, statRes] = await Promise.all([
          coreApi.get(`/datasets/${datasetId}`),
          coreApi.get(`/images/${datasetId}/images`, { params: { per_page: 50 } }),
          coreApi.get(`/datasets/${datasetId}/stats`),
        ])
        setDataset(dsRes.data)
        setImages(imgRes.data.items || [])
        setStats(statRes.data)
      } finally {
        setLoading(false)
      }
    }
    if (datasetId) fetchData()
  }, [datasetId])

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    try {
      const formData = new FormData()
      files.forEach((f) => formData.append('files', f))
      await coreApi.post(`/images/${datasetId}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      // Refresh images
      const imgRes = await coreApi.get(`/images/${datasetId}/images`, { params: { per_page: 50 } })
      setImages(imgRes.data.items || [])
    } finally {
      setUploading(false)
    }
  }

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>

  return (
    <div className="p-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/projects" className="hover:text-gray-900">Projects</Link>
        <ChevronRight className="w-4 h-4" />
        <Link to={`/projects/${projectId}`} className="hover:text-gray-900">Project</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-gray-900 font-medium">{dataset?.name}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{dataset?.name}</h1>
          {stats && (
            <p className="text-gray-500 mt-1">
              {stats.total_images} images
              {stats.by_status?.annotated ? ` · ${stats.by_status.annotated} annotated` : ''}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Link
            to={`/projects/${projectId}/annotate`}
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Annotate
          </Link>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={handleUpload}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            <Upload className="w-4 h-4" />
            {uploading ? 'Uploading...' : 'Upload Images'}
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total', value: stats.total_images, color: 'text-gray-700' },
            { label: 'Unannotated', value: stats.by_status?.unannotated || 0, color: 'text-yellow-600' },
            { label: 'In Progress', value: stats.by_status?.in_progress || 0, color: 'text-blue-600' },
            { label: 'Annotated', value: stats.by_status?.annotated || 0, color: 'text-green-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-lg p-4 border border-gray-100 text-center">
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-gray-500 mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Image grid */}
      {images.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200">
          <Upload className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 mb-3">No images yet. Upload some images to get started.</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Upload images
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-8 gap-2">
          {images.map((img) => (
            <Link
              key={img.id}
              to={`/projects/${projectId}/annotate/${img.id}`}
              className="group relative aspect-square rounded-lg overflow-hidden bg-gray-100 border border-gray-200 hover:border-blue-400"
            >
              {img.thumb_url ? (
                <img
                  src={img.thumb_url}
                  alt={img.filename}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-300 text-xs">
                  {img.filename?.slice(-8)}
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              {img.annotation_status === 'annotated' && (
                <div className="absolute top-1 right-1 w-2 h-2 bg-green-400 rounded-full" />
              )}
              {img.annotation_status === 'in_progress' && (
                <div className="absolute top-1 right-1 w-2 h-2 bg-blue-400 rounded-full" />
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
