import { useAuthStore } from '../store/authStore'

export function Settings() {
  const { user } = useAuthStore()

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="max-w-2xl space-y-6">
        {/* Profile */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Profile</h2>
          <dl className="space-y-3">
            <div className="flex items-center justify-between">
              <dt className="text-sm text-gray-500">Email</dt>
              <dd className="text-sm font-medium text-gray-900">{user?.email}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-sm text-gray-500">Full Name</dt>
              <dd className="text-sm font-medium text-gray-900">{user?.fullName || '—'}</dd>
            </div>
          </dl>
        </div>

        {/* API Keys */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h2 className="text-base font-semibold text-gray-900 mb-2">API Keys</h2>
          <p className="text-sm text-gray-500 mb-4">
            Use API keys to authenticate requests to the inference endpoint.
          </p>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
            Generate API Key
          </button>
        </div>

        {/* About */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h2 className="text-base font-semibold text-gray-900 mb-2">About VisionForge</h2>
          <p className="text-sm text-gray-500">
            VisionForge is a comprehensive machine vision platform for dataset management,
            model training, and deployment.
          </p>
          <p className="text-xs text-gray-400 mt-3">Version 1.0.0</p>
        </div>
      </div>
    </div>
  )
}
