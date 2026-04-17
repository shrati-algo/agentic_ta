import { Circle, User } from "lucide-react";
import { NavLink } from "react-router-dom";

import { ROUTES } from "../routes";

interface Props {
  connected?: boolean;
  sessionId?: string | null;
}

export function Header({ connected, sessionId }: Props) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-slate-900 text-sm font-bold text-white">
            algo8
          </div>
          <span className="text-sm font-semibold tracking-wide text-slate-600">
            MARUTI
          </span>
        </div>

        <nav className="flex items-center gap-1">
          <NavLink
            to={ROUTES.home}
            className={({ isActive }) =>
              `rounded px-3 py-1.5 text-sm font-medium transition ${
                isActive
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            Home
          </NavLink>
          <NavLink
            to={ROUTES.settings}
            className={({ isActive }) =>
              `rounded px-3 py-1.5 text-sm font-medium transition ${
                isActive
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            Settings
          </NavLink>
        </nav>

        <div className="flex items-center gap-3">
          {sessionId && (
            <span className="flex items-center gap-1.5 text-xs text-slate-600">
              <Circle
                className={`h-2 w-2 ${
                  connected ? "fill-green-500 text-green-500" : "fill-amber-400 text-amber-400"
                }`}
              />
              {connected ? "Live" : "Reconnecting"}
            </span>
          )}
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200"
            aria-label="user menu"
          >
            <User className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
