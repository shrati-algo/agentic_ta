import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ROUTES } from "../routes";

/**
 * Maruti-Inspection-styled sign-in page. See the reference screenshot:
 * two-column layout, product name + algo8 footer on the left, sign-in
 * form on the right. Accepts any non-empty credentials (demo gate only).
 */
export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn } = useAuth();

  const [username, setUsername] = useState("devteam@algo8.ai");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTo =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? ROUTES.home;

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("Username and password are required.");
      return;
    }
    setError(null);
    signIn(username.trim());
    navigate(redirectTo, { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-5xl bg-white shadow-xl rounded-md grid grid-cols-1 md:grid-cols-2 overflow-hidden border border-slate-200">
        {/* Left panel: product branding */}
        <div className="relative flex flex-col items-center justify-center p-10 border-b md:border-b-0 md:border-r border-slate-200">
          <div className="flex flex-col items-center gap-4">
            <MarutiLogo />
            <h1 className="text-2xl font-medium text-slate-800 tracking-wide">
              Maruti Inspection
            </h1>
          </div>

          <div className="absolute left-6 bottom-6 flex items-end gap-2">
            <Algo8WordMark />
            <span className="text-[11px] text-slate-500 mb-1">an algo8.ai product</span>
          </div>
          <div className="absolute right-6 bottom-6 text-xs text-slate-500">
            <span className="text-sky-700 font-semibold">Plant</span>
            <span className="text-amber-500 font-semibold">Brain</span>
            <sup className="text-slate-400">TM</sup>
          </div>
        </div>

        {/* Right panel: sign-in form */}
        <form onSubmit={onSubmit} className="flex flex-col justify-center p-10 gap-5">
          <h2 className="text-2xl font-semibold text-slate-800">Sign In</h2>

          <label className="flex flex-col gap-1.5">
            <span className="text-sm text-slate-600">Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="h-10 rounded-full border border-slate-300 bg-sky-50 px-4 text-sm outline-none focus:ring-2 focus:ring-sky-300"
              autoComplete="username"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-sm text-slate-600">Password</span>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 w-full rounded-full border border-slate-300 bg-sky-50 px-4 pr-10 text-sm outline-none focus:ring-2 focus:ring-sky-300"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
              >
                <EyeIcon open={showPassword} />
              </button>
            </div>
          </label>

          {error && (
            <div role="alert" className="text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end">
            <button
              type="submit"
              className="inline-flex items-center gap-2 bg-sky-700 hover:bg-sky-800 text-white text-sm font-medium px-5 h-10 rounded-full shadow"
            >
              <ArrowIcon />
              Sign In
            </button>
          </div>

          <p className="text-sm text-slate-500">
            First time signing in?{" "}
            <a href="#create-password" className="text-sky-700 underline hover:text-sky-900">
              Create a password
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}

function MarutiLogo() {
  // Simple stylised "M" mark matching the screenshot colours.
  return (
    <svg width="72" height="72" viewBox="0 0 64 64" aria-hidden="true">
      <path
        d="M4 52 L4 12 L20 12 L32 32 L44 12 L60 12 L60 52 L48 52 L48 28 L36 46 L28 46 L16 28 L16 52 Z"
        fill="#2F53A7"
      />
    </svg>
  );
}

function Algo8WordMark() {
  return (
    <div className="flex items-baseline">
      <span className="text-2xl font-bold text-sky-600 tracking-tight">algo</span>
      <span className="text-2xl font-extrabold text-fuchsia-600">8</span>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12h14M13 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M3 3l18 18M10.58 10.58a2 2 0 002.83 2.83M9.9 4.24A9.99 9.99 0 0112 4c6.5 0 10 7 10 7a13.16 13.16 0 01-3.17 4.04M6.1 6.1C3.5 7.9 2 12 2 12s3.5 7 10 7c1.5 0 2.9-.26 4.2-.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
