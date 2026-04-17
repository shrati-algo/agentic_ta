import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { ViolationDetail } from "./pages/ViolationDetail";
import { ROUTES } from "./routes";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path={ROUTES.login} element={<Login />} />
          <Route path="/" element={<Navigate to={ROUTES.home} replace />} />
          <Route
            path={ROUTES.home}
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.detailPattern}
            element={
              <ProtectedRoute>
                <ViolationDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="*"
            element={
              <div className="p-8 text-slate-600">
                <h1 className="text-lg font-semibold">Not found</h1>
                <p className="text-sm">The page you requested doesn’t exist.</p>
              </div>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
