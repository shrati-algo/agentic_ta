import { useMemo, useState } from "react";
import { MoreVertical, Plus, Search } from "lucide-react";

import { Header } from "../components/Header";
import { useLiveSession } from "../hooks/useLiveSession";

/**
 * Settings page -- User Management sub-section.
 * Deliberately uses placeholder users distinct from any screenshot.
 * Pure UI: no backend, no persistence. Wiring to a real user store is
 * EPIC-13 / EPIC-14 territory.
 */

type Role = "SuperAdmin" | "Admin" | "User";
type Shift = "A" | "B" | "C";

interface UserRow {
  name: string;
  employeeId: string;
  email: string;
  phone: string;
  shift: Shift;
  role: Role;
}

const PLACEHOLDER_USERS: UserRow[] = [
  {
    name: "Priya Sharma",
    employeeId: "PS001",
    email: "priya.sharma@algo8.ai",
    phone: "9876500001",
    shift: "A",
    role: "SuperAdmin",
  },
  {
    name: "Rajesh Kumar",
    employeeId: "RK042",
    email: "rajesh.k@algo8.ai",
    phone: "9876500002",
    shift: "A",
    role: "Admin",
  },
  {
    name: "Anita Verma",
    employeeId: "AV117",
    email: "anita.verma@algo8.ai",
    phone: "9876500003",
    shift: "B",
    role: "Admin",
  },
  {
    name: "Karthik Iyer",
    employeeId: "KI203",
    email: "karthik.iyer@algo8.ai",
    phone: "9876500004",
    shift: "A",
    role: "User",
  },
  {
    name: "Meera Patel",
    employeeId: "MP308",
    email: "meera.patel@algo8.ai",
    phone: "9876500005",
    shift: "C",
    role: "User",
  },
  {
    name: "Arjun Reddy",
    employeeId: "AR422",
    email: "arjun.reddy@algo8.ai",
    phone: "9876500006",
    shift: "B",
    role: "User",
  },
];

export function Settings() {
  const { sessionId, connected } = useLiveSession();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return PLACEHOLDER_USERS;
    return PLACEHOLDER_USERS.filter((u) =>
      [u.name, u.employeeId, u.email, u.phone, u.role].some((v) =>
        v.toLowerCase().includes(q)
      )
    );
  }, [query]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header connected={connected} sessionId={sessionId} />

      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="flex gap-6">
          {/* Left sidebar */}
          <aside className="w-56 shrink-0 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Settings</h2>
            <nav className="flex flex-col gap-1 text-sm">
              <button
                type="button"
                className="rounded-md bg-sky-50 px-3 py-2 text-left text-sky-700"
              >
                User Management
              </button>
            </nav>
          </aside>

          {/* Right content */}
          <section className="flex-1 rounded-lg border border-slate-200 bg-white p-5">
            <div className="mb-4 flex items-center justify-between gap-4">
              <h3 className="text-base font-semibold text-slate-800">User Management</h3>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search..."
                    className="h-9 w-64 rounded-full border border-slate-300 bg-white pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-sky-200"
                  />
                </div>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600"
                >
                  <Plus className="h-4 w-4" />
                  Add New User
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Employee ID</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Phone</th>
                    <th className="px-4 py-3">Shift</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="w-10 px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {filtered.map((u) => (
                    <tr key={u.employeeId} className="hover:bg-slate-50">
                      <td className="px-4 py-3">{u.name}</td>
                      <td className="px-4 py-3">{u.employeeId}</td>
                      <td className="px-4 py-3">{u.email}</td>
                      <td className="px-4 py-3">{u.phone}</td>
                      <td className="px-4 py-3">{u.shift}</td>
                      <td className="px-4 py-3">{u.role}</td>
                      <td className="px-4 py-3 text-slate-400">
                        <button
                          type="button"
                          aria-label={`Actions for ${u.name}`}
                          className="rounded p-1 hover:bg-slate-100 hover:text-slate-700"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                        No users match "{query}".
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
