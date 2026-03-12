import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { Dashboard } from './pages/Dashboard'
import { Projects } from './pages/Projects'
import { ProjectDetail } from './pages/ProjectDetail'
import { DatasetDetail } from './pages/DatasetDetail'
import { Annotate } from './pages/Annotate'
import { Train } from './pages/Train'
import { TrainingJobDetail } from './pages/TrainingJobDetail'
import { ModelRegistry } from './pages/ModelRegistry'
import { Deploy } from './pages/Deploy'
import { Workflows } from './pages/Workflows'
import { WorkflowEditorPage } from './pages/WorkflowEditorPage'
import { Settings } from './pages/Settings'
import { Login } from './pages/Login'
import { useAuthStore } from './store/authStore'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <AppShell />
            </PrivateRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
          <Route path="projects/:projectId" element={<ProjectDetail />} />
          <Route path="projects/:projectId/datasets/:datasetId" element={<DatasetDetail />} />
          <Route path="projects/:projectId/annotate/:imageId?" element={<Annotate />} />
          <Route path="projects/:projectId/train" element={<Train />} />
          <Route path="projects/:projectId/train/:jobId" element={<TrainingJobDetail />} />
          <Route path="projects/:projectId/registry" element={<ModelRegistry />} />
          <Route path="projects/:projectId/deploy" element={<Deploy />} />
          <Route path="workflows" element={<Workflows />} />
          <Route path="workflows/:workflowId/edit" element={<WorkflowEditorPage />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
