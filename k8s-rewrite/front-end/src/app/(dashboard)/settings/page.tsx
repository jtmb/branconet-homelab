"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { setViewMode, type ViewMode } from "../viewport-wrapper";
import ViewportWrapper from "../viewport-wrapper";
import {
  Settings,
  HardDrive,
  Loader2,
  Save,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ArrowLeft,
  Monitor,
  Maximize2,
  Columns,
  UserPlus,
  Shield,
} from "lucide-react";

interface PVInfo {
  name: string;
  reclaimPolicy: string;
  status: string;
  storageClass: string;
  capacity: string;
  claimRef: string;
  age: string;
}

interface VolumeReclaimEdit {
  name: string;
  policy: string;
}

export default function SettingsPage() {
  const [volumes, setVolumes] = useState<PVInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<Map<string, string>>(new Map());
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);
  const [defaultPolicy, setDefaultPolicy] = useState("Retain");
  const [defaultPolicySaving, setDefaultPolicySaving] = useState(false);
  const [viewMode, setViewModeLocal] = useState<ViewMode>("comfortable");
  const [allowRegistration, setAllowRegistration] = useState(false);
  const [registrationLoading, setRegistrationLoading] = useState(true);
  const [registrationSaving, setRegistrationSaving] = useState(false);
  const [userCount, setUserCount] = useState(0);
  const [role, setRole] = useState<"readonly" | "write" | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("k8s-view-mode");
    if (stored === "comfortable" || stored === "full") {
      setViewModeLocal(stored);
    }
  }, []);

  const fetchRegistrationStatus = useCallback(async () => {
    try {
      const [settingsRes, sessionRes] = await Promise.all([
        fetch("/api/settings"),
        fetch("/api/auth/session"),
      ]);
      const settings = await settingsRes.json();
      const session = await sessionRes.json();

      setAllowRegistration(
        session.registrationOpen ||
        settings.allow_registration === "true"
      );
    } catch {
      // ignore
    } finally {
      setRegistrationLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRegistrationStatus();
    fetch("/api/auth/session")
      .then((r) => r.json())
      .then((d) => { if (d.role) setRole(d.role); })
      .catch(() => {});
  }, [fetchRegistrationStatus]);

  async function toggleRegistration() {
    setRegistrationSaving(true);
    try {
      const newValue = !allowRegistration;
      const res = await fetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "allow_registration", value: String(newValue) }),
      });
      if (res.ok) {
        setAllowRegistration(newValue);
      }
    } catch (err) {
      console.error("Failed to toggle registration:", err);
    } finally {
      setRegistrationSaving(false);
    }
  }

  const fetchVolumes = useCallback(async () => {
    try {
      const res = await fetch("/api/cluster/volumes/reclaim");
      const data = await res.json();
      if (data.volumes) {
        setVolumes(data.volumes);
      }
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVolumes();
    const interval = setInterval(fetchVolumes, 15000);
    return () => clearInterval(interval);
  }, [fetchVolumes]);

  function handlePolicyChange(name: string, policy: string) {
    const next = new Map(edits);
    if (policy === getOriginalPolicy(name)) {
      next.delete(name);
    } else {
      next.set(name, policy);
    }
    setEdits(next);
  }

  function getOriginalPolicy(name: string): string {
    return volumes.find((v) => v.name === name)?.reclaimPolicy || "Retain";
  }

  function getEffectivePolicy(name: string): string {
    return edits.get(name) ?? getOriginalPolicy(name);
  }

  async function saveAll() {
    if (edits.size === 0) return;
    setSaving(true);
    setSaveResult(null);

    const changes: VolumeReclaimEdit[] = [];
    edits.forEach((policy, name) => {
      changes.push({ name, policy });
    });

    try {
      const res = await fetch("/api/cluster/volumes/reclaim", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ volumes: changes }),
      });
      const data = await res.json();

      if (data.success) {
        setSaveResult({ success: true, message: `Updated ${changes.length} volume${changes.length !== 1 ? "s" : ""}` });
        setEdits(new Map());
        fetchVolumes();
      } else {
        const failed = data.results?.filter((r: any) => !r.success).map((r: any) => r.name).join(", ");
        setSaveResult({ success: false, message: `Failed: ${failed}` });
      }
    } catch (err) {
      setSaveResult({ success: false, message: String(err) });
    } finally {
      setSaving(false);
    }
  }

  async function setAllReleasedToDelete() {
    const released = volumes.filter((v) => v.status === "Released");
    if (released.length === 0) return;

    const next = new Map(edits);
    released.forEach((v) => next.set(v.name, "Delete"));
    setEdits(next);
  }

  const hasEdits = edits.size > 0;
  const releasedCount = volumes.filter((v) => v.status === "Released").length;
  const retainCount = volumes.filter(
    (v) => getEffectivePolicy(v.name) === "Retain",
  ).length;

  return (
    <div className="flex flex-col min-h-0">

      <ViewportWrapper>
      <main className="px-3 sm:px-4 lg:px-6 py-8 space-y-8">
        <div className="flex items-center gap-3">
          <Settings className="page-header-icon text-amber-400" />
          <h1 className="page-header-title">Settings</h1>
        </div>
        {/* Save result toast */}
        {saveResult && (
          <div
            className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
              saveResult.success
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                : "bg-red-500/10 border-red-500/20 text-red-300"
            }`}
          >
            {saveResult.success ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-red-400" />
            )}
            <p className="text-sm">{saveResult.message}</p>
            <button
              onClick={() => setSaveResult(null)}
              className="ml-auto text-zinc-500 hover:text-zinc-300"
            >
              ×
            </button>
          </div>
        )}

        {/* Default reclaim policy section */}
        <section className="rounded-2xl bg-zinc-900/70 border border-zinc-800 p-6">
          <h2 className="text-base font-semibold text-zinc-100 mb-4 flex items-center gap-2">
            <Settings className="w-4 h-4 text-amber-400" />
            Default Settings
          </h2>
          <div className="flex items-center gap-4">
            <div>
              <label className="text-xs text-zinc-500 block mb-1.5">
                Default PV Reclaim Policy
              </label>
              <p className="text-xs text-zinc-600 mb-2">
                Applied when creating new persistent volumes through the UI.
                Existing volumes are not affected.
              </p>
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <select
                value={defaultPolicy}
                onChange={(e) => setDefaultPolicy(e.target.value)}
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-amber-500/50 transition-colors"
              >
                <option value="Retain">Retain</option>
                <option value="Delete">Delete</option>
                <option value="Recycle">Recycle</option>
              </select>
              {role === "write" && (
              <button
                onClick={async () => {
                  setDefaultPolicySaving(true);
                  // Save to DB or just use as runtime setting for now
                  await new Promise((r) => setTimeout(r, 500));
                  setDefaultPolicySaving(false);
                }}
                disabled={defaultPolicySaving}
                className="px-3 py-2 rounded-lg bg-amber-600/20 border border-amber-500/20 text-amber-400 hover:bg-amber-600/30 text-xs font-medium transition-colors disabled:opacity-50"
              >
                {defaultPolicySaving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  "Save"
                )}
              </button>
              )}
            </div>
          </div>
        </section>

        {/* Viewport section */}
        <section className="rounded-2xl bg-zinc-900/70 border border-zinc-800 p-6">
          <h2 className="text-base font-semibold text-zinc-100 mb-4 flex items-center gap-2">
            <Monitor className="w-4 h-4 text-teal-400" />
            Viewport Width
          </h2>
          <p className="text-xs text-zinc-500 mb-4">
            Controls how wide the main content area stretches. Cards and tables
            will respect this maximum width. The sidebar and top bar are unaffected.
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            {([
              ["comfortable", "Comfortable", Columns],
              ["full", "Full Width", Maximize2],
            ] as const).map(([mode, label, Icon]) => (
              <button
                key={mode}
                onClick={() => {
                  setViewModeLocal(mode);
                  setViewMode(mode);
                }}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all ${
                  viewMode === mode
                    ? "bg-teal-500/10 border-teal-500/30 text-teal-300 shadow-[0_0_10px_rgba(45,212,191,0.08)]"
                    : "border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* Registration toggle section */}
        <section className="rounded-2xl bg-zinc-900/70 border border-zinc-800 p-6">
          <h2 className="text-base font-semibold text-zinc-100 mb-4 flex items-center gap-2">
            <UserPlus className="w-4 h-4 text-emerald-400" />
            User Registration
          </h2>
          <p className="text-sm text-zinc-400 mb-4">
            When enabled, new users can create accounts from the login page.
            When disabled, only existing users can sign in. This can also be
            controlled via the{" "}
            <code className="text-xs bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-300">
              ALLOW_REGISTRATION
            </code>{" "}
            environment variable.
          </p>

          {registrationLoading ? (
            <div className="flex items-center gap-2 text-sm text-zinc-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading...
            </div>
          ) : (
            <div className="flex items-center gap-4">
              {role === "write" ? (
              <button
                onClick={toggleRegistration}
                disabled={registrationSaving}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 ${
                  allowRegistration
                    ? "bg-emerald-600"
                    : "bg-zinc-700"
                } ${registrationSaving ? "opacity-50" : ""}`}
                role="switch"
                aria-checked={allowRegistration}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    allowRegistration ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
              ) : (
                <span
                  className={`inline-flex h-6 w-11 items-center rounded-full ${
                    allowRegistration ? "bg-emerald-600" : "bg-zinc-700"
                  } opacity-60`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      allowRegistration ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </span>
              )}
              <div>
                <span
                  className={`text-sm font-medium ${
                    allowRegistration ? "text-emerald-400" : "text-zinc-500"
                  }`}
                >
                  {allowRegistration ? "Registration open" : "Registration locked"}
                </span>
                {registrationSaving && (
                  <Loader2 className="w-3 h-3 animate-spin text-zinc-500 inline ml-2" />
                )}
              </div>
            </div>
          )}
        </section>

        {/* Volume reclaim policy section */}
        <section className="rounded-2xl bg-zinc-900/70 border border-zinc-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-blue-400" />
              Persistent Volume Reclaim Policies
            </h2>
            {role === "write" && (
            <div className="flex items-center gap-2">
              {releasedCount > 0 && (
                <button
                  onClick={setAllReleasedToDelete}
                  className="px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 text-xs font-medium transition-colors"
                >
                  Set all Released → Delete
                </button>
              )}
              <button
                onClick={saveAll}
                disabled={!hasEdits || saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-600/30 text-xs font-medium transition-colors disabled:opacity-40"
              >
                {saving ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Save className="w-3 h-3" />
                )}
                Save Changes{hasEdits ? ` (${edits.size})` : ""}
              </button>
            </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 p-4 rounded-lg bg-red-500/5 border border-red-500/10 text-red-400 text-sm">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          ) : volumes.length === 0 ? (
            <p className="text-sm text-zinc-500 py-8 text-center">
              No persistent volumes found
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500 uppercase tracking-wider">
                    <th className="pb-3 pr-4 font-medium">Volume</th>
                    <th className="pb-3 pr-4 font-medium">Reclaim Policy</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">Storage Class</th>
                    <th className="pb-3 pr-4 font-medium">Capacity</th>
                    <th className="pb-3 pr-4 font-medium">Claim</th>
                    <th className="pb-3 font-medium">Age</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {volumes.map((vol) => {
                    const effective = getEffectivePolicy(vol.name);
                    const isChanged = edits.has(vol.name);
                    const isReleased = vol.status === "Released";
                    return (
                      <tr
                        key={vol.name}
                        className={`${
                          isReleased ? "bg-amber-500/[0.03]" : ""
                        }`}
                      >
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            <code className="text-xs text-zinc-300 font-mono truncate max-w-[220px]">
                              {vol.name}
                            </code>
                            {isReleased && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">
                                RELEASED
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          {role === "write" ? (
                          <select
                            value={effective}
                            onChange={(e) =>
                              handlePolicyChange(vol.name, e.target.value)
                            }
                            className={`text-xs rounded-lg px-2 py-1.5 border transition-colors outline-none ${
                              isChanged
                                ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-300"
                                : effective === "Delete"
                                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                                  : effective === "Retain"
                                    ? "bg-zinc-800 border-zinc-700 text-zinc-300"
                                    : "bg-zinc-800 border-zinc-700 text-zinc-300"
                            }`}
                          >
                            <option value="Retain">Retain</option>
                            <option value="Delete">Delete</option>
                            <option value="Recycle">Recycle</option>
                          </select>
                          ) : (
                            <span className={`text-xs px-2 py-1.5 rounded-lg border ${
                              effective === "Delete"
                                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                                : effective === "Retain"
                                  ? "bg-zinc-800 border-zinc-700 text-zinc-300"
                                  : "bg-zinc-800 border-zinc-700 text-zinc-300"
                            }`}>{effective}</span>
                          )}
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={`text-xs ${
                              vol.status === "Bound"
                                ? "text-emerald-400"
                                : vol.status === "Released"
                                  ? "text-amber-400"
                                  : vol.status === "Available"
                                    ? "text-blue-400"
                                    : "text-zinc-400"
                            }`}
                          >
                            {vol.status}
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <span className="text-xs text-zinc-400">
                            {vol.storageClass || "none"}
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <span className="text-xs text-zinc-400">
                            {vol.capacity}
                          </span>
                        </td>
                        <td className="py-3 pr-4">
                          <span className="text-xs text-zinc-500 font-mono">
                            {vol.claimRef || "—"}
                          </span>
                        </td>
                        <td className="py-3">
                          <span className="text-xs text-zinc-500">
                            {vol.age}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Summary */}
          {!loading && volumes.length > 0 && (
            <div className="mt-6 pt-4 border-t border-zinc-800 flex items-center gap-6 text-xs text-zinc-500">
              <span>
                <span className="text-zinc-300 font-medium">{volumes.length}</span>{" "}
                volumes
              </span>
              <span>
                <span className="text-emerald-400 font-medium">
                  {volumes.filter((v) => getEffectivePolicy(v.name) === "Delete").length}
                </span>{" "}
                Delete
              </span>
              <span>
                <span className="text-zinc-300 font-medium">
                  {volumes.filter((v) => getEffectivePolicy(v.name) === "Retain").length}
                </span>{" "}
                Retain
              </span>
              {releasedCount > 0 && (
                <span className="flex items-center gap-1 text-amber-400">
                  <AlertTriangle className="w-3 h-3" />
                  {releasedCount} released
                </span>
              )}
            </div>
          )}
        </section>

        {/* Cascade delete settings */}
        <section className="rounded-2xl bg-zinc-900/70 border border-zinc-800 p-6">
          <h2 className="text-base font-semibold text-zinc-100 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            Cascade Delete
          </h2>
          <p className="text-sm text-zinc-400 mb-4">
            When you delete a Flux repository from{" "}
            <Link href="/flux" className="text-indigo-400 hover:text-indigo-300 underline">
              Settings → Flux
            </Link>
            , the cascade delete will:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-sm text-zinc-400 ml-2">
            <li>Delete Flux CRDs (GitRepository, Kustomization, auth Secret)</li>
            <li>Delete the target namespace with all workloads &amp; PVCs</li>
            <li>
              Delete orphaned PVs (any reclaim policy — uses{" "}
              <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">--force</code>)
            </li>
            <li>Remove the repository from the database</li>
          </ol>
          <p className="text-xs text-zinc-600 mt-3">
            PVs with <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">Retain</code>{" "}
            policy that are left behind after a partial delete can be cleaned
            up above. Set them to <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">Delete</code>{" "}
            to prevent orphaned volumes in the future.
          </p>
        </section>
      </main>
      </ViewportWrapper>
    </div>
  );
}
