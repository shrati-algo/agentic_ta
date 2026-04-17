import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "./AuthContext";
import { ROUTES } from "../routes";

/**
 * Guard-rail component: renders its children only when the user is
 * authenticated. Unauthenticated hits redirect to the login page and
 * pass the current location in state so we can bounce the user back
 * after sign-in.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace state={{ from: location }} />;
  }
  return <>{children}</>;
}
