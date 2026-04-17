import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

/**
 * Minimal client-side auth gate.
 *
 * Wraps the app in a context that remembers whether the user has signed
 * in during this page-load. Refreshing the page sends them back to the
 * login screen -- deliberate: per CLAUDE.md we do not persist auth state
 * in localStorage or sessionStorage. A real backend-backed session is
 * EPIC-13 territory.
 */
type AuthState = {
  isAuthenticated: boolean;
  username: string | null;
  signIn(username: string): void;
  signOut(): void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);

  const value = useMemo<AuthState>(
    () => ({
      isAuthenticated: username !== null,
      username,
      signIn: (u: string) => setUsername(u),
      signOut: () => setUsername(null),
    }),
    [username]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
