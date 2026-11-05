import { useState } from "react";
import { createRoot } from "react-dom/client";
import { KvWorkbench, type KvCapabilities, type KvSelectedPath } from "../src/components/secrets/kv-workbench";
const initial: KvSelectedPath = { id: "11111111-1111-1111-1111-111111111111", mountId: "22222222-2222-2222-2222-222222222222", path: "apps/api", namespace: "apps", name: "original", revision: 7,
  fields: [{ field: "text", key: "original_under_score" }, { field: "empty", key: "zero" }, { field: "binary", key: "bytes" }] };
const caps: KvCapabilities = { pathId: initial.id, revision: 7, permissions: { list: true, read: true, create: true, update: true, delete: true, rollback: true, reconcile: true, export: true }, nativeMutationEnabled: true, initializationAllowed: true };
function Fixture() {
  const [open, setOpen] = useState(false), [path, setPath] = useState(initial), [refreshes, setRefreshes] = useState(0);
  return <main className="min-h-screen bg-zinc-950 p-4 text-zinc-100">
    <button id="open" onClick={() => setOpen(true)}>Open synthetic workbench</button>
    <button id="switch" onClick={() => setPath({ ...initial, id: "33333333-3333-3333-3333-333333333333", path: "apps/other" })}>Switch fixture path</button>
    <button id="revision" onClick={() => setPath({ ...path, revision: path.revision + 1 })}>Change metadata revision</button>
    <p>Metadata refresh callbacks: {refreshes}</p>
    {open && <KvWorkbench path={path} capabilities={caps} onClose={() => setOpen(false)} onMetadataRefresh={() => setRefreshes(count => count + 1)} returnFocus={() => document.getElementById("open")?.focus()} />}
  </main>;
}
createRoot(document.getElementById("root")!).render(<Fixture />);
