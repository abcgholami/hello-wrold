import axios, { type AxiosInstance } from 'axios'
import { useAuthStore } from '../store/authStore'

function createClient(baseURL: string): AxiosInstance {
  const client = axios.create({ baseURL })

  client.interceptors.request.use((config) => {
    const token = useAuthStore.getState().accessToken
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  client.interceptors.response.use(
    (res) => res,
    async (error) => {
      if (error.response?.status === 401) {
        // Try refresh
        try {
          const refreshRes = await axios.post('/api/core/auth/refresh', {}, { withCredentials: true })
          const newToken = refreshRes.data.access_token
          useAuthStore.getState().setToken(newToken)
          error.config.headers.Authorization = `Bearer ${newToken}`
          return client.request(error.config)
        } catch {
          useAuthStore.getState().logout()
          window.location.href = '/login'
        }
      }
      return Promise.reject(error)
    }
  )

  return client
}

export const coreApi = createClient('/api/core')
export const trainApi = createClient('/api/train')
export const inferApi = createClient('/api/infer')
export const aiApi = createClient('/api/ai')
