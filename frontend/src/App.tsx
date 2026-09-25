import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { Spinner } from '@/components/ui'
import { AgentConsole } from '@/pages/AgentConsole'
import { Analytics } from '@/pages/Analytics'
import { HelpCentre } from '@/pages/HelpCentre'
import { KnowledgeAdmin } from '@/pages/KnowledgeAdmin'
import { Login } from '@/pages/Login'
import { MyOrders } from '@/pages/MyOrders'
import { Storefront } from '@/pages/Storefront'
import { Support } from '@/pages/Support'
import { Tickets } from '@/pages/Tickets'
import { isStaff, useAuth } from '@/store/auth'

function FullPageSpinner() {
  return (
    <div className="flex h-full items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  )
}

function RequireAuth({ children, staffOnly = false }: {
  children: React.ReactNode
  staffOnly?: boolean
}) {
  const { user, initialised } = useAuth()
  const location = useLocation()

  if (!initialised) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (staffOnly && !isStaff(user)) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const { bootstrap, initialised } = useAuth()

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  if (!initialised) return <FullPageSpinner />

  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<AppShell />}>
        <Route index element={<Support />} />
        <Route path="store" element={<Storefront />} />
        <Route path="support" element={<Navigate to="/" replace />} />
        <Route path="help" element={<HelpCentre />} />
        <Route
          path="orders"
          element={
            <RequireAuth>
              <MyOrders />
            </RequireAuth>
          }
        />

        <Route path="console">
          <Route index element={<Navigate to="/console/conversations" replace />} />
          <Route
            path="conversations"
            element={
              <RequireAuth staffOnly>
                <AgentConsole />
              </RequireAuth>
            }
          />
          <Route
            path="tickets"
            element={
              <RequireAuth staffOnly>
                <Tickets />
              </RequireAuth>
            }
          />
          <Route
            path="knowledge"
            element={
              <RequireAuth staffOnly>
                <KnowledgeAdmin />
              </RequireAuth>
            }
          />
          <Route
            path="analytics"
            element={
              <RequireAuth staffOnly>
                <Analytics />
              </RequireAuth>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
