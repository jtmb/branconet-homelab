"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  MoreHorizontal,
  FileCode,
  Download,
  Trash2,
  RotateCcw,
  RefreshCw,
  Terminal,
  ScrollText,
  Pencil,
  Plus,
  Minus,
  Pause,
  Undo2,
  FolderOpen,
  Play,
  ShieldOff,
  Shield,
} from "lucide-react";
import YamlModal from "./yaml-modal";
import ConfirmDialog from "./confirm-dialog";
import LogModal from "./log-modal";

export type ResourceType = "pod" | "deployment" | "namespace" | "node" | "ingress";

interface ActionItem {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

interface Props {
  resourceType: ResourceType;
  resource: any;
  onAction?: () => void;
}

export default function ResourceActionsMenu({ resourceType, resource, onAction }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Modal state
  const [yamlModal, setYamlModal] = useState<{
    open: boolean;
    yaml: string;
    title: string;
    readOnly: boolean;
    saveUrl: string;
  }>({ open: false, yaml: "", title: "", readOnly: true, saveUrl: "" });
  const [logModal, setLogModal] = useState<{
    open: boolean;
    logs: string;
    title: string;
  }>({ open: false, logs: "", title: "" });
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    danger: boolean;
    onConfirm: () => void;
  }>({
    open: false,
    title: "",
    message: "",
    confirmLabel: "Confirm",
    danger: false,
    onConfirm: () => {},
  });
  const [dialogLoading, setDialogLoading] = useState(false);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }, []);

  const ns = resource?.metadata?.namespace || "";
  const name = resource?.metadata?.name || resource?.name || "";

  // ── YAML helpers ────────────────────────────────────────────
  const fetchYaml = async (apiPath: string): Promise<string> => {
    const res = await fetch(apiPath);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.yaml;
  };

  const openViewYaml = async (apiPath: string, title: string) => {
    try {
      const yaml = await fetchYaml(apiPath);
      setYamlModal({ open: true, yaml, title, readOnly: true, saveUrl: "" });
    } catch (e: any) {
      showToast(`Failed to load YAML: ${e?.message}`);
    }
  };

  const openEditYaml = async (apiPath: string, title: string) => {
    try {
      const yaml = await fetchYaml(apiPath);
      setYamlModal({ open: true, yaml, title, readOnly: false, saveUrl: apiPath });
    } catch (e: any) {
      showToast(`Failed to load YAML: ${e?.message}`);
    }
  };

  const downloadYaml = async (apiPath: string, filename: string) => {
    try {
      const yaml = await fetchYaml(apiPath);
      const blob = new Blob([yaml], { type: "application/x-yaml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      showToast("YAML downloaded");
    } catch (e: any) {
      showToast(`Download failed: ${e?.message}`);
    }
  };

  const handleYamlSave = async (yaml: string): Promise<void> => {
    const res = await fetch(yamlModal.saveUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data?.error || `HTTP ${res.status}`);
    }
    showToast("YAML applied successfully");
  };

  // ── Delete helper ───────────────────────────────────────────
  const promptDelete = (apiPath: string, resourceLabel: string, redirectUrl: string) => {
    setConfirmDialog({
      open: true,
      title: `Delete ${resourceLabel}`,
      message: `Are you sure you want to delete "${name}"? This action cannot be undone.`,
      confirmLabel: "Delete",
      danger: true,
      onConfirm: async () => {
        setDialogLoading(true);
        try {
          const res = await fetch(apiPath, { method: "DELETE" });
          if (!res.ok) {
            const data = await res.json();
            throw new Error(data?.error || `HTTP ${res.status}`);
          }
          showToast(`${resourceLabel} deleted`);
          setConfirmDialog((p) => ({ ...p, open: false }));
          router.push(redirectUrl);
          router.refresh();
        } catch (e: any) {
          showToast(`Delete failed: ${e?.message}`);
        } finally {
          setDialogLoading(false);
        }
      },
    });
  };

  // ── Actions ─────────────────────────────────────────────────
  const actions = getActions(resourceType, resource, ns, name, {
    openViewYaml,
    openEditYaml,
    downloadYaml,
    promptDelete,
    showToast,
    router,
    setLogModal,
    setConfirmDialog,
    onAction,
  });

  return (
    <>
      <div ref={ref} className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="p-1 rounded-lg hover:bg-zinc-800 transition-colors"
          aria-label="Resource actions"
        >
          <MoreHorizontal className="w-5 h-5 text-zinc-400" />
        </button>
        {open && (
          <div className="dropdown right-0 top-full mt-1 min-w-[180px]">
            {actions.map((a) => (
              <button
                key={a.label}
                onClick={() => {
                  a.onClick();
                  setOpen(false);
                }}
                disabled={a.disabled}
                className={`dropdown-item flex items-center gap-2.5 ${
                  a.danger
                    ? "text-red-400 hover:bg-red-500/10"
                    : ""
                } ${a.disabled ? "opacity-40 cursor-not-allowed" : ""}`}
              >
                <span className="w-4 h-4 flex-shrink-0">{a.icon}</span>
                <span>{a.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl bg-zinc-800 border border-zinc-700 text-sm text-zinc-200 shadow-lg">
          {toast}
        </div>
      )}

      {/* Modals */}
      <YamlModal
        open={yamlModal.open}
        onClose={() => setYamlModal((p) => ({ ...p, open: false }))}
        yaml={yamlModal.yaml}
        title={yamlModal.title}
        readOnly={yamlModal.readOnly}
        onSave={yamlModal.readOnly ? undefined : handleYamlSave}
      />

      <LogModal
        open={logModal.open}
        onClose={() => setLogModal((p) => ({ ...p, open: false }))}
        logs={logModal.logs}
        title={logModal.title}
      />

      <ConfirmDialog
        open={confirmDialog.open}
        onClose={() => setConfirmDialog((p) => ({ ...p, open: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmLabel={confirmDialog.confirmLabel}
        danger={confirmDialog.danger}
        loading={dialogLoading}
      />
    </>
  );
}

interface ActionHelpers {
  openViewYaml: (apiPath: string, title: string) => Promise<void>;
  openEditYaml: (apiPath: string, title: string) => Promise<void>;
  downloadYaml: (apiPath: string, filename: string) => Promise<void>;
  promptDelete: (apiPath: string, label: string, redirectUrl: string) => void;
  showToast: (msg: string) => void;
  router: ReturnType<typeof useRouter>;
  setLogModal: (v: { open: boolean; logs: string; title: string }) => void;
  setConfirmDialog: (v: any) => void;
  onAction?: () => void;
}

function getActions(
  type: ResourceType,
  resource: any,
  ns: string,
  name: string,
  h: ActionHelpers
): ActionItem[] {
  switch (type) {
    // ── Pod Actions ────────────────────────────────────────────
    case "pod": {
      const yamlPath = `/api/cluster/pods/${ns}/${name}/yaml`;
      const logsPath = `/api/cluster/pods/${ns}/${name}/logs`;
      const deletePath = `/api/cluster/pods/${ns}/${name}/delete`;

      return [
        {
          label: "View Logs",
          icon: <ScrollText className="w-4 h-4" />,
          onClick: async () => {
            try {
              const res = await fetch(logsPath);
              const data = await res.json();
              h.setLogModal({
                open: true,
                logs: data.logs || "",
                title: `Logs: ${ns}/${name}`,
              });
            } catch (e: any) {
              h.showToast(`Failed to load logs: ${e?.message}`);
            }
          },
        },
        {
          label: "Execute Shell",
          icon: <Terminal className="w-4 h-4" />,
          onClick: () => h.router.push(`/pods/${ns}/${name}/shell`),
        },
        {
          label: "View YAML",
          icon: <FileCode className="w-4 h-4" />,
          onClick: () => h.openViewYaml(yamlPath, `Pod YAML: ${ns}/${name}`),
        },
        {
          label: "Edit YAML",
          icon: <Pencil className="w-4 h-4" />,
          onClick: () => h.openEditYaml(yamlPath, `Edit Pod YAML: ${ns}/${name}`),
        },
        {
          label: "Download YAML",
          icon: <Download className="w-4 h-4" />,
          onClick: () => h.downloadYaml(yamlPath, `pod-${ns}-${name}.yaml`),
        },
        {
          label: "Delete",
          icon: <Trash2 className="w-4 h-4" />,
          onClick: () => h.promptDelete(deletePath, "Pod", "/pods"),
          danger: true,
        },
      ];
    }

    // ── Deployment Actions ─────────────────────────────────────
    case "deployment": {
      const yamlPath = `/api/cluster/deployments/${ns}/${name}/yaml`;
      const deletePath = `/api/cluster/deployments/${ns}/${name}/delete`;
      const scalePath = `/api/cluster/deployments/${ns}/${name}/scale`;
      const actionPath = `/api/cluster/deployments/${ns}/${name}/action`;

      const replicas = resource?.spec?.replicas ?? resource?.replicas ?? 1;
      const isPaused = resource?.spec?.paused ?? resource?.paused ?? false;

      const doAction = async (action: string, label: string) => {
        try {
          const res = await fetch(actionPath, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action }),
          });
          if (!res.ok) {
            const d = await res.json();
            throw new Error(d?.error || `HTTP ${res.status}`);
          }
          h.showToast(`${label} triggered`);
          h.router.refresh();
        } catch (e: any) {
          h.showToast(`${label} failed: ${e?.message}`);
        }
      };

      const doScale = async (delta: number) => {
        const newReplicas = Math.max(0, (replicas || 1) + delta);
        try {
          const res = await fetch(scalePath, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ replicas: newReplicas }),
          });
          if (!res.ok) {
            const d = await res.json();
            throw new Error(d?.error || `HTTP ${res.status}`);
          }
          h.showToast(`Scaled to ${newReplicas} replicas`);
          h.router.refresh();
          h.onAction?.();
        } catch (e: any) {
          h.showToast(`Scale failed: ${e?.message}`);
        }
      };

      return [
        {
          label: "Redeploy",
          icon: <RotateCcw className="w-4 h-4" />,
          onClick: () => doAction("restart", "Redeploy"),
        },
        {
          label: "Rollback",
          icon: <Undo2 className="w-4 h-4" />,
          onClick: () => doAction("rollback", "Rollback"),
        },
        {
          label: "Restart",
          icon: <RefreshCw className="w-4 h-4" />,
          onClick: () => doAction("restart", "Restart"),
        },
        {
          label: "Scale Up",
          icon: <Plus className="w-4 h-4" />,
          onClick: () => doScale(1),
          disabled: isPaused,
        },
        {
          label: "Scale Down",
          icon: <Minus className="w-4 h-4" />,
          onClick: () => doScale(-1),
          disabled: isPaused || replicas <= 0,
        },
        {
          label: isPaused ? "Resume" : "Pause",
          icon: isPaused ? (
            <Play className="w-4 h-4" />
          ) : (
            <Pause className="w-4 h-4" />
          ),
          onClick: () => doAction(isPaused ? "resume" : "pause", isPaused ? "Resume" : "Pause"),
        },
        {
          label: "View YAML",
          icon: <FileCode className="w-4 h-4" />,
          onClick: () => h.openViewYaml(yamlPath, `Deployment YAML: ${ns}/${name}`),
        },
        {
          label: "Edit YAML",
          icon: <Pencil className="w-4 h-4" />,
          onClick: () => h.openEditYaml(yamlPath, `Edit Deployment YAML: ${ns}/${name}`),
        },
        {
          label: "Download YAML",
          icon: <Download className="w-4 h-4" />,
          onClick: () => h.downloadYaml(yamlPath, `deployment-${ns}-${name}.yaml`),
        },
        {
          label: "Delete",
          icon: <Trash2 className="w-4 h-4" />,
          onClick: () => h.promptDelete(deletePath, "Deployment", "/deployments"),
          danger: true,
        },
      ];
    }

    // ── Namespace Actions ──────────────────────────────────────
    case "namespace": {
      const yamlPath = `/api/cluster/namespaces/${name}/yaml`;
      const deletePath = `/api/cluster/namespaces/${name}/delete`;

      return [
        {
          label: "View YAML",
          icon: <FileCode className="w-4 h-4" />,
          onClick: () => h.openViewYaml(yamlPath, `Namespace YAML: ${name}`),
        },
        {
          label: "Edit YAML",
          icon: <Pencil className="w-4 h-4" />,
          onClick: () => h.openEditYaml(yamlPath, `Edit Namespace YAML: ${name}`),
        },
        {
          label: "Download YAML",
          icon: <Download className="w-4 h-4" />,
          onClick: () => h.downloadYaml(yamlPath, `namespace-${name}.yaml`),
        },
        {
          label: "Move",
          icon: <FolderOpen className="w-4 h-4" />,
          onClick: () => h.showToast("Move — not supported via kubectl"),
          disabled: true,
        },
        {
          label: "Delete",
          icon: <Trash2 className="w-4 h-4" />,
          onClick: () => h.promptDelete(deletePath, "Namespace", "/name-spaces"),
          danger: true,
        },
      ];
    }

    // ── Node Actions ───────────────────────────────────────────
    case "node": {
      const yamlPath = `/api/cluster/nodes/${name}/yaml`;
      const actionPath = `/api/cluster/nodes/${name}/action`;

      const isCordoned = resource?.spec?.unschedulable ?? false;

      const doAction = async (action: string, label: string) => {
        try {
          const res = await fetch(actionPath, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action }),
          });
          if (!res.ok) {
            const d = await res.json();
            throw new Error(d?.error || `HTTP ${res.status}`);
          }
          h.showToast(`${label} triggered`);
          h.router.refresh();
        } catch (e: any) {
          h.showToast(`${label} failed: ${e?.message}`);
        }
      };

      return [
        {
          label: isCordoned ? "Uncordon" : "Cordon",
          icon: isCordoned ? <Shield className="w-4 h-4" /> : <ShieldOff className="w-4 h-4" />,
          onClick: () => doAction(isCordoned ? "uncordon" : "cordon", isCordoned ? "Uncordon" : "Cordon"),
        },
        {
          label: "Drain",
          icon: <Trash2 className="w-4 h-4" />,
          onClick: () => doAction("drain", "Drain"),
          danger: true,
        },
        {
          label: "View YAML",
          icon: <FileCode className="w-4 h-4" />,
          onClick: () => h.openViewYaml(yamlPath, `Node YAML: ${name}`),
        },
        {
          label: "Download YAML",
          icon: <Download className="w-4 h-4" />,
          onClick: () => h.downloadYaml(yamlPath, `node-${name}.yaml`),
        },
      ];
    }

    // ── Ingress Actions ────────────────────────────────────────
    case "ingress": {
      const yamlPath = `/api/cluster/ingresses/${ns}/${name}/yaml`;
      const deletePath = `/api/cluster/ingresses/${ns}/${name}/delete`;

      return [
        {
          label: "View YAML",
          icon: <FileCode className="w-4 h-4" />,
          onClick: () => h.openViewYaml(yamlPath, `Ingress YAML: ${ns}/${name}`),
        },
        {
          label: "Edit YAML",
          icon: <Pencil className="w-4 h-4" />,
          onClick: () => h.openEditYaml(yamlPath, `Edit Ingress YAML: ${ns}/${name}`),
        },
        {
          label: "Download YAML",
          icon: <Download className="w-4 h-4" />,
          onClick: () => h.downloadYaml(yamlPath, `ingress-${ns}-${name}.yaml`),
        },
        {
          label: "Delete",
          icon: <Trash2 className="w-4 h-4" />,
          onClick: () => h.promptDelete(deletePath, "Ingress", "/ingresses"),
          danger: true,
        },
      ];
    }

    default:
      return [];
  }
}
