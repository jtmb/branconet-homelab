"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  UsersRound, Search, Plus, Pencil, Trash2, Save, Loader2,
  Shield, ShieldCheck, AlertTriangle, CheckCircle2, X,
} from "lucide-react";
import ViewportWrapper from "../viewport-wrapper";
import { SortHeader, useSort } from "@/components/ui/sortable-header";

interface UserData {
  id: string;
  username: string;
  role: "readonly" | "write";
  createdAt: string;
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [currentRole, setCurrentRole] = useState<"readonly" | "write" | null>(null);

  // Add modal state
  const [adding, setAdding] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"readonly" | "write">("readonly");
  const [addError, setAddError] = useState<string | null>(null);
  const [addSaving, setAddSaving] = useState(false);

  // Edit modal state
  const [editing, setEditing] = useState<UserData | null>(null);
  const [editRole, setEditRole] = useState<"readonly" | "write">("readonly");
  const [editPassword, setEditPassword] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  // Delete confirmation
  const [deleting, setDeleting] = useState<UserData | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSaving, setDeleteSaving] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    fetch("/api/auth/session")
      .then((r) => r.json())
      .then((d) => { if (d.role) setCurrentRole(d.role); })
      .catch(() => {});
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      const res = await fetch("/api/users");
      setUsers(await res.json());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const isWrite = currentRole === "write";

  const { sortKey, sortDir, toggle: toggleSort } = useSort("username");

  const filteredUsers = useMemo(() => {
    let result = search.trim()
      ? users.filter((u) => u.username.toLowerCase().includes(search.toLowerCase()))
      : users;
    return [...result].sort((a, b) => {
      const va = String((a as any)[sortKey] ?? "").toLowerCase();
      const vb = String((b as any)[sortKey] ?? "").toLowerCase();
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }, [users, search, sortKey, sortDir]);

  function showToast(success: boolean, message: string) {
    setToast({ success, message });
    setTimeout(() => setToast(null), 3000);
  }

  async function addUser() {
    if (!newUsername.trim() || !newPassword) return;
    setAddSaving(true);
    setAddError(null);
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword,
          role: newRole,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setNewUsername("");
        setNewPassword("");
        setNewRole("readonly");
        setAdding(false);
        fetchUsers();
        showToast(true, `User "${data.username}" created`);
      } else {
        setAddError(data.error || "Failed to create user");
      }
    } catch {
      setAddError("Network error");
    } finally {
      setAddSaving(false);
    }
  }

  function startEdit(u: UserData) {
    setEditing(u);
    setEditRole(u.role);
    setEditPassword("");
    setEditError(null);
  }

  async function saveEdit() {
    if (!editing) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const body: { role?: string; password?: string } = {};
      if (editRole !== editing.role) body.role = editRole;
      if (editPassword.trim()) body.password = editPassword.trim();

      if (Object.keys(body).length === 0) {
        setEditing(null);
        return;
      }

      const res = await fetch(`/api/users/${editing.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setEditing(null);
        fetchUsers();
        showToast(true, `User "${editing.username}" updated`);
      } else {
        setEditError(data.error || "Failed to update user");
      }
    } catch {
      setEditError("Network error");
    } finally {
      setEditSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteSaving(true);
    setDeleteError(null);
    try {
      const res = await fetch(`/api/users/${deleting.id}`, { method: "DELETE" });
      const data = await res.json();
      if (res.ok) {
        setDeleting(null);
        fetchUsers();
        showToast(true, `User "${deleting.username}" deleted`);
      } else {
        setDeleteError(data.error || "Failed to delete user");
      }
    } catch {
      setDeleteError("Network error");
    } finally {
      setDeleteSaving(false);
    }
  }

  function formatAge(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(dateStr).toLocaleDateString();
  }

  return (
    <div className="flex flex-col min-h-0">
      <ViewportWrapper>
        <main className="px-3 sm:px-4 lg:px-6 py-6">
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <UsersRound className="page-header-icon text-emerald-400" />
            <h1 className="page-header-title">Users</h1>
            <span className="text-sm text-zinc-500 ml-auto">
              {loading ? "…" : `${users.length} users`}
            </span>
          </div>

          {/* Toast */}
          {toast && (
            <div
              className={`flex items-center gap-3 px-4 py-3 rounded-xl border mb-6 ${
                toast.success
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                  : "bg-red-500/10 border-red-500/20 text-red-300"
              }`}
            >
              {toast.success ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-red-400" />
              )}
              <p className="text-sm">{toast.message}</p>
              <button
                onClick={() => setToast(null)}
                className="ml-auto text-zinc-500 hover:text-zinc-300"
              >
                ×
              </button>
            </div>
          )}

          {/* Filter Bar */}
          <div className="flex items-center gap-3 mb-6">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <input
                type="text"
                placeholder="Search users…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  width: "100%",
                  background: "rgb(39,39,42)",
                  border: "none",
                  outline: "none",
                  boxShadow: "none",
                  padding: "0.5rem 0.75rem 0.5rem 2.25rem",
                  fontSize: "0.875rem",
                  lineHeight: "1.25rem",
                  color: "#e4e4e7",
                  borderRadius: "0.5rem",
                  WebkitAppearance: "none",
                  MozAppearance: "none",
                  appearance: "none",
                }}
              />
            </div>

            {isWrite && (
              <button
                onClick={() => {
                  setAdding(true);
                  setAddError(null);
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors ml-auto"
              >
                <Plus className="w-4 h-4" />
                Add User
              </button>
            )}
          </div>

          {/* Table */}
          {loading ? (
            <div className="flex items-center justify-center min-h-[calc(100vh-20rem)]">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="glass-card p-8 rounded-xl text-center">
              <UsersRound className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Users Found</h3>
              <p className="text-sm text-zinc-500">
                {search ? "No users match your search." : "Add users above."}
              </p>
            </div>
          ) : (
            <div className="glass-card rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-700/40">
                    <th className="text-left px-4 py-3">
                      <SortHeader label="Username" active={sortKey === "username"} dir={sortDir} onClick={() => toggleSort("username")} />
                    </th>
                    <th className="text-left px-4 py-3">
                      <SortHeader label="Role" active={sortKey === "role"} dir={sortDir} onClick={() => toggleSort("role")} />
                    </th>
                    <th className="text-left px-4 py-3">
                      <SortHeader label="Created" active={sortKey === "createdAt"} dir={sortDir} onClick={() => toggleSort("createdAt")} />
                    </th>
                    {isWrite && (
                      <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400">
                        Actions
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="border-b border-zinc-800/40 hover:bg-zinc-800/30">
                      <td className="px-4 py-2.5 text-sm font-medium text-zinc-200">
                        {user.username}
                      </td>
                      <td className="px-4 py-2.5">
                        {user.role === "write" ? (
                          <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <ShieldCheck className="w-3 h-3" />
                            Write
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-zinc-700/50 text-zinc-400 border border-zinc-700">
                            <Shield className="w-3 h-3" />
                            Read Only
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-sm text-zinc-500">
                        {formatAge(user.createdAt)}
                      </td>
                      {isWrite && (
                        <td className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => startEdit(user)}
                              className="p-1.5 rounded-lg hover:bg-zinc-700/50 text-zinc-500 hover:text-zinc-300 transition-colors"
                              title="Edit user"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                setDeleting(user);
                                setDeleteError(null);
                              }}
                              className="p-1.5 rounded-lg hover:bg-red-500/10 text-zinc-500 hover:text-red-400 transition-colors"
                              title="Delete user"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Add User Modal */}
          {adding && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => { if (!addSaving) setAdding(false); }}>
              <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-sm mx-4 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-700/40">
                  <h3 className="text-sm font-semibold text-zinc-200">Add User</h3>
                  <button onClick={() => setAdding(false)} disabled={addSaving} className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-5 flex flex-col gap-3">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Username</label>
                    <input
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      placeholder="e.g. john.doe"
                      className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Password</label>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Min 8 characters"
                      className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Role</label>
                    <select
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value as "readonly" | "write")}
                      className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-colors"
                    >
                      <option value="readonly">Read Only</option>
                      <option value="write">Write</option>
                    </select>
                  </div>
                  {addError && (
                    <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{addError}</p>
                  )}
                </div>
                <div className="px-5 py-3 border-t border-zinc-700/40 flex items-center justify-end gap-2">
                  <button
                    onClick={() => setAdding(false)}
                    disabled={addSaving}
                    className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={addUser}
                    disabled={!newUsername.trim() || !newPassword || addSaving}
                    className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {addSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    Create
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Edit User Modal */}
          {editing && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => { if (!editSaving) setEditing(null); }}>
              <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-sm mx-4 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-700/40">
                  <h3 className="text-sm font-semibold text-zinc-200">Edit: {editing.username}</h3>
                  <button onClick={() => setEditing(null)} disabled={editSaving} className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-5 flex flex-col gap-3">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Role</label>
                    <select
                      value={editRole}
                      onChange={(e) => setEditRole(e.target.value as "readonly" | "write")}
                      className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-colors"
                    >
                      <option value="readonly">Read Only</option>
                      <option value="write">Write</option>
                    </select>
                    {editing.role === "write" && editRole === "readonly" && (
                      <p className="text-xs text-amber-400 mt-1.5">Demoting to Read Only will revoke their write access.</p>
                    )}
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">New Password (leave blank to keep current)</label>
                    <input
                      type="password"
                      value={editPassword}
                      onChange={(e) => setEditPassword(e.target.value)}
                      placeholder="Min 8 characters"
                      className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-colors"
                    />
                  </div>
                  {editError && (
                    <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{editError}</p>
                  )}
                </div>
                <div className="px-5 py-3 border-t border-zinc-700/40 flex items-center justify-end gap-2">
                  <button
                    onClick={() => setEditing(null)}
                    disabled={editSaving}
                    className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveEdit}
                    disabled={editSaving || (editRole === editing.role && !editPassword.trim())}
                    className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {editSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    Save
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Delete Confirmation Modal */}
          {deleting && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => { if (!deleteSaving) setDeleting(null); }}>
              <div className="bg-zinc-900 border border-zinc-700/60 rounded-2xl w-full max-w-sm mx-4 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-700/40">
                  <h3 className="text-sm font-semibold text-zinc-200">Delete User</h3>
                  <button onClick={() => setDeleting(null)} disabled={deleteSaving} className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                      <AlertTriangle className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-200">
                        Delete <span className="text-red-400">{deleting.username}</span>?
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {deleting.role === "write" ? "This user has write access." : "This user is read-only."}
                        {" "}This action cannot be undone.
                      </p>
                    </div>
                  </div>
                  {deleteError && (
                    <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2 mb-3">{deleteError}</p>
                  )}
                </div>
                <div className="px-5 py-3 border-t border-zinc-700/40 flex items-center justify-end gap-2">
                  <button
                    onClick={() => setDeleting(null)}
                    disabled={deleteSaving}
                    className="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={confirmDelete}
                    disabled={deleteSaving}
                    className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {deleteSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </ViewportWrapper>
    </div>
  );
}
