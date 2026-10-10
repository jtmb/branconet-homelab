"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useSession } from "@/lib/use-query";
import { useMutation } from "@/lib/use-mutation";
import { QueryStatus } from "@/components/ui/query-status";
import { ResourceTable } from "@/components/cluster/resource-list";
import ViewportWrapper from "../viewport-wrapper";
const Modal = dynamic(() => import("@/components/ui/modal").then(module => module.Modal), { ssr: false });
const ConfirmDialog = dynamic(() => import("../confirm-dialog"), { ssr: false });

type UserRow = Record<string, unknown> & { id: string; username: string; role: "readonly" | "write"; createdAt: string };
const blank = { username: "", password: "", role: "readonly" as "readonly" | "write" };
export default function UsersPage() {
  const query = useQuery<UserRow[]>("/api/users");
  const session = useSession();
  const mutation = useMutation();
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<"new" | UserRow>();
  const [form, setForm] = useState(blank);
  const [deleting, setDeleting] = useState<UserRow>();
  const [message, setMessage] = useState("");
  useEffect(() => { if (!session.canWrite) { setEditor(undefined); setDeleting(undefined); setForm(blank); } }, [session.canWrite]);
  const editing = editor && editor !== "new" ? editor : undefined;
  const dirty = editing ? form.role !== editing.role || form.password !== "" : true;
  const valid = editor === "new"
    ? /^[a-zA-Z0-9_-]{3,30}$/.test(form.username) && form.password.length >= 8
    : dirty && (form.password === "" || form.password.length >= 8);
  const rows = query.data?.filter(user => user.username.toLowerCase().includes(search.toLowerCase()));
  function open(user?: UserRow) {
    mutation.clear(); setMessage(""); setEditor(user ?? "new");
    setForm(user ? { username: user.username, password: "", role: user.role } : blank);
  }
  function close() { if (!mutation.busy) { setEditor(undefined); setForm(blank); mutation.clear(); } }
  function save() {
    if (!session.canWrite || !editor || !valid) return;
    const body = editing
      ? { ...(form.role !== editing.role ? { role: form.role } : {}), ...(form.password !== "" ? { password: form.password } : {}) }
      : form;
    void mutation.mutate(editing ? "/api/users/" + encodeURIComponent(editing.id) : "/api/users", {
      method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }, () => {
      setEditor(undefined); setForm(blank); setMessage(editing ? "User updated." : "User created."); query.refetch(); session.refetch();
    });
  }
  return <ViewportWrapper><main className="min-w-0 space-y-4 px-3 py-6 sm:px-4 lg:px-6">
    <h1 className="text-2xl font-semibold">Users</h1>
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    <div className="flex flex-wrap items-end gap-3">
      <label className="text-sm">Search users<input value={search} onChange={e => setSearch(e.target.value)} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-900 p-2" /></label>
      {session.canWrite && <button onClick={() => open()} disabled={mutation.busy} className="rounded bg-indigo-600 px-3 py-2 disabled:opacity-50">Add user</button>}
    </div>
    <QueryStatus query={query} />
    {query.loading ? <p role="status">Loading users…</p> : rows && <ResourceTable rows={rows} resetKey={search}
      columns={[{ key: "username", label: "Username" }, { key: "role", label: "Role" }, { key: "createdAt", label: "Created", sort: "date" }]}
      renderActions={session.canWrite ? row => {
        const user = row as UserRow;
        return <div className="flex gap-3">
          <button aria-label={"Edit user " + user.username} disabled={mutation.busy} onClick={() => open(user)} className="text-indigo-300 underline">Edit</button>
          {user.username !== session.data?.username && <button aria-label={"Delete user " + user.username} disabled={mutation.busy} onClick={() => { mutation.clear(); setDeleting(user); }} className="text-red-300 underline">Delete</button>}
        </div>;
      } : undefined} />}
    {editor && session.canWrite && <Modal open title={editing ? "Edit user " + editing.username : "Add user"} onClose={close}
      description={editing ? "Role changes take effect on the next request. A password reset ends the user's existing sessions." : "Create an account with an explicit role."}>
      <form onSubmit={e => { e.preventDefault(); save(); }} className="space-y-4">
        {!editing && <label className="block text-sm">Username<input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
          autoComplete="off" required minLength={3} maxLength={30} pattern="[a-zA-Z0-9_-]+" disabled={mutation.busy} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-2" /></label>}
        <label className="block text-sm">{editing ? "New password (leave empty to keep it)" : "Password (at least 8 characters)"}
          <input type="password" autoComplete="new-password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
            required={!editing} minLength={8} disabled={mutation.busy} className="mt-1 block w-full rounded border border-zinc-700 bg-zinc-950 p-2" /></label>
        <label className="block text-sm">Role<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value as UserRow["role"] })}
          disabled={mutation.busy || editing?.username === session.data?.username} className="mt-1 block rounded border border-zinc-700 bg-zinc-950 p-2"><option value="readonly">Read only</option><option value="write">Write</option></select></label>
        {mutation.error && <p role="alert" className="text-red-300">{mutation.error}</p>}
        <div className="flex flex-wrap justify-end gap-3"><button type="button" onClick={close} disabled={mutation.busy} className="rounded bg-zinc-700 px-4 py-2">Cancel</button>
          <button disabled={!valid || mutation.busy} className="rounded bg-indigo-600 px-4 py-2 disabled:opacity-50">{mutation.busy ? "Saving…" : editing ? "Save user" : "Create user"}</button></div>
      </form>
    </Modal>}
    {deleting && session.canWrite && <ConfirmDialog key={deleting.id} open title="Delete user" message={"Remove the account and end all its sessions: " + deleting.username}
      confirmName={deleting.username} loading={mutation.busy} error={mutation.error} danger confirmLabel="Delete user"
      onClose={() => { if (!mutation.busy) setDeleting(undefined); }} onConfirm={() => {
        if (!session.canWrite) return;
        void mutation.mutate("/api/users/" + encodeURIComponent(deleting.id), { method: "DELETE" }, () => { setDeleting(undefined); setMessage("User deleted."); query.refetch(); });
      }} />}
  </main></ViewportWrapper>;
}
