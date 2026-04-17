import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Dashboard } from "./pages/Dashboard";
import { ViolationDetail } from "./pages/ViolationDetail";
import { ROUTES } from "./routes";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={ROUTES.home} replace />} />
        <Route path={ROUTES.home} element={<Dashboard />} />
        <Route path={ROUTES.detailPattern} element={<ViolationDetail />} />
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
  );
}
