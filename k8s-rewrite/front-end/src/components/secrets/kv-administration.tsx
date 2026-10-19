"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/use-query";
import {
  ADMIN_ACTIONS,
  AdminCancelled,
  AdminInputError,
  AdminFailure,
  AdministrationClient,
  appendImpact,
  canAct,
  consumerTarget,
  destroyBody,
  gcBody,
  historyConfirmation,
  identityConfirmation,
  impactAcknowledgement,
  isUuid,
  pathConfirmation,
  policyConfirmation,
  type AdminAction,
  type Audit,
  type Capabilities,
  type CleanupResult,
  type ConsumerPreview,
  type GcPreview,
  type Grant,
  type Identity,
  type IdentityScope,
  type ImpactPage,
  type ImpactSnapshot,
  type LegacyPrincipal,
  type NativeStatus,
  type Operation,
  type Page,
  type PathMetadata,
  type PathSnapshot,
  type Policy,
  type PolicyFields,
  type Rotation,
  type Versions,
} from "./kv-administration-model";

/** Owner integration: selectedPathId is an explicit registered UUID, never an inferred alias.
 * Bump refreshKey after external metadata changes. Unmount (or set active=false) on close/logout.
 * onMetadataChange fires only after a confirmed response, and contains metadata scope only.
 * No value/token enters the shared query cache, callback, URL, browser storage or logs.
 */
export type KvAdministrationProps = {
  selectedPathId?: string | null;
  refreshKey?: string | number;
  active?: boolean;
  initialOpen?: boolean;
  onClose?: () => void;
  onMetadataChange?: (
    scope:
      | "policies"
      | "identities"
      | "legacy"
      | "paths"
      | "history"
      | "rotations"
      | "recovery",
  ) => void;
};
type Changed = NonNullable<KvAdministrationProps["onMetadataChange"]>;
type Request = <T>(url: string, method?: string, body?: unknown) => Promise<T>;
const inputClass =
  "w-full min-w-0 rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400";
const buttonClass =
  "rounded border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 hover:bg-zinc-700 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-40";
const dangerClass = buttonClass + " border-rose-800 text-rose-200";
const boxClass =
  "min-w-0 space-y-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4";
const noop: Changed = () => {};
const route = (id: string) => `/api/kv/paths/${encodeURIComponent(id)}`;
function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block min-w-0 space-y-1 text-sm text-zinc-300">
      <span>{label}</span>
      {children}
      {hint && <span className="block text-xs text-zinc-400">{hint}</span>}
    </label>
  );
}
function Button({
  children,
  onClick,
  disabled,
  danger = false,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      className={danger ? dangerClass : buttonClass}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
function Check({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-start gap-2 text-sm text-zinc-300">
      <input
        type="checkbox"
        className="mt-1 accent-indigo-500"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="min-w-0 break-all">{label}</span>
    </label>
  );
}
function Actions({
  value,
  onChange,
}: {
  value: AdminAction[];
  onChange: (value: AdminAction[]) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm text-zinc-300">
        Allowed operations in this rule
      </legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {ADMIN_ACTIONS.map((action) => (
          <Check
            key={action}
            label={action}
            checked={value.includes(action)}
            onChange={(checked) =>
              onChange(
                checked
                  ? [...value, action]
                  : value.filter((item) => item !== action),
              )
            }
          />
        ))}
      </div>
    </fieldset>
  );
}
function Exact({
  label = "Type the complete captured confirmation",
  expected,
  value,
  onChange,
}: {
  label?: string;
  expected: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-400">{label}</p>
      <code className="block break-all rounded bg-zinc-950 p-2 text-xs text-indigo-200">
        {expected}
      </code>
      <Field label="Exact confirmation">
        <input
          className={inputClass}
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </Field>
    </div>
  );
}
function useTask(clearSensitive: () => void = () => {}) {
  const clearRef = useRef(clearSensitive);
  clearRef.current = clearSensitive;
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [operationId, setOperationId] = useState("");
  const client = useRef<AdministrationClient | null>(null),
    mounted = useRef(true),
    running = useRef(false);
  if (!client.current)
    client.current = new AdministrationClient(fetch, () => clearRef.current());
  useEffect(() => {
    mounted.current = true;
    const clear = () => {
      client.current?.invalidate();
      clearRef.current();
    };
    const hidden = () => {
      if (document.visibilityState === "hidden") clear();
    };
    window.addEventListener("bortus-session-ended", clear);
    window.addEventListener("pagehide", clear);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      mounted.current = false;
      clear();
      window.removeEventListener("bortus-session-ended", clear);
      window.removeEventListener("pagehide", clear);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, []);
  const run = useCallback(
    async <T,>(
      work: (request: Request) => Promise<T>,
      done: (result: T) => void,
      admin = true,
    ) => {
      if (running.current) return;
      running.current = true;
      setBusy(true);
      setError("");
      setOperationId("");
      try {
        const result = await client.current!.run(work, admin);
        if (mounted.current) done(result);
      } catch (failure) {
        if (mounted.current && !(failure instanceof AdminCancelled)) {
          setError(
            failure instanceof Error
              ? failure.message
              : "Request failed; inspect metadata.",
          );
          if (failure instanceof AdminFailure)
            setOperationId(failure.operationId ?? "");
        }
      } finally {
        running.current = false;
        if (mounted.current) setBusy(false);
      }
    },
    [],
  );
  return { busy, error, operationId, run };
}
type Task = ReturnType<typeof useTask>;
function TaskState({ task }: { task: Task }) {
  return (
    <div aria-live="polite" className="space-y-1 text-sm">
      {task.busy && (
        <p className="text-indigo-300" role="status">
          Request in progress…
        </p>
      )}
      {task.error && (
        <p className="break-words text-rose-300" role="alert">
          {task.error}
        </p>
      )}
      {task.operationId && (
        <p className="break-all text-amber-300">
          Recovery operation: {task.operationId}. Inspect it before another
          mutation.
        </p>
      )}
    </div>
  );
}
function usePage<T>(base: string | null, admin = true, clearSensitive?: () => void) {
  const task = useTask(() => {
      setPage(null);
      setCursor(null);
      setPrevious([]);
      clearSensitive?.();
    }),
    [page, setPage] = useState<Page<T> | null>(null),
    [cursor, setCursor] = useState<string | null>(null),
    [previous, setPrevious] = useState<(string | null)[]>([]);
  const { run } = task;
  const load = useCallback(
    (next: string | null = null) => {
      setPage(null);
      if (base === null) return;
      void run(
        (request) =>
          request<Page<T>>(
            base +
              (next
                ? `${base.includes("?") ? "&" : "?"}cursor=${encodeURIComponent(next)}`
                : ""),
          ),
        (result) => {
          if (result.items.length > 100)
            throw new AdminInputError("Metadata page exceeds the row limit.");
          setPage(result);
          setCursor(next);
        },
        admin,
      );
    },
    [base, admin, run],
  );
  useEffect(() => {
    setPrevious([]);
    setCursor(null);
    load();
  }, [load]);
  return {
    task,
    page,
    refresh: () => {
      setPrevious([]);
      load();
    },
    controls: (
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={base === null || task.busy || !previous.length}
          onClick={() => {
            const stack = [...previous],
              next = stack.pop() ?? null;
            setPrevious(stack);
            load(next);
          }}
        >
          Previous page
        </Button>
        <Button
          disabled={base === null || task.busy || !page?.nextCursor}
          onClick={() => {
            setPrevious([...previous.slice(-99), cursor]);
            load(page!.nextCursor);
          }}
        >
          Next page
        </Button>
        <Button
          disabled={base === null || task.busy}
          onClick={() => {
            setPrevious([]);
            load();
          }}
        >
          Refresh metadata
        </Button>
      </div>
    ),
  };
}
function Table({
  headings,
  children,
}: {
  headings: string[];
  children: ReactNode;
}) {
  return (
    <div className="max-w-full overflow-x-auto rounded border border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-950 text-zinc-400">
          <tr>
            {headings.map((heading) => (
              <th key={heading} scope="col" className="px-3 py-2 font-medium">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800 [&_td]:px-3 [&_td]:py-2 [&_td]:align-top">
          {children}
        </tbody>
      </table>
    </div>
  );
}
function Impact({
  snapshot,
  next,
  busy,
  aliasesChecked,
  setAliasesChecked,
  configurationChecked,
  setConfigurationChecked,
}: {
  snapshot: ImpactSnapshot;
  next: () => void;
  busy: boolean;
  aliasesChecked: boolean;
  setAliasesChecked: (value: boolean) => void;
  configurationChecked: boolean;
  setConfigurationChecked: (value: boolean) => void;
}) {
  return (
    <div className="space-y-3 rounded border border-amber-900 p-3">
      <p className="text-sm text-amber-200">
        Reviewed {snapshot.aliases.length} of {snapshot.page.affectedAliasCount}{" "}
        affected aliases.{" "}
        {snapshot.complete
          ? "Complete preview captured."
          : "Review the next page before committing."}
      </p>
      <Table
        headings={["Exact alias / target", "Before → after", "Metadata basis"]}
      >
        {snapshot.page.items.map((row) => (
          <tr key={row.alias}>
            <td className="break-all">
              {row.alias}
              <br />
              <span className="text-xs text-zinc-400">
                {row.namespace}/{row.name}/{row.key}
                <br />
                path revision {row.pathRevision ?? "none"}; mount revision{" "}
                {row.mountRevision ?? "none"}
              </span>
            </td>
            <td>
              {row.beforeAllowed ? "Allowed" : "Denied"} →{" "}
              {row.afterAllowed ? "Allowed" : "Denied"}
            </td>
            <td>{row.basis}</td>
          </tr>
        ))}
      </Table>
      {!snapshot.complete && (
        <Button disabled={busy} onClick={next}>
          Review next impact page
        </Button>
      )}
      <p className="text-xs text-zinc-400">
        Authorization metadata only. Native ownership, head, drift, key
        presence, collisions and availability are checked separately at lookup.
        External alias-file changes are not transactional with SQLite.
      </p>
      {snapshot.page.required && (
        <Check
          label={`I acknowledge the complete impact on all ${snapshot.page.affectedAliasCount} exact aliases reviewed across these pages.`}
          checked={aliasesChecked}
          disabled={!snapshot.complete}
          onChange={setAliasesChecked}
        />
      )}
      {snapshot.page.nonsecretConfigurationAffected && (
        <Check
          label="I acknowledge this principal also controls nonsecret configuration lookup."
          checked={configurationChecked}
          disabled={!snapshot.complete}
          onChange={setConfigurationChecked}
        />
      )}
    </div>
  );
}

function Policies({ changed }: { changed: Changed }) {
  const [editing, setEditing] = useState<Policy | null>(null),
    [mode, setMode] = useState<"create" | "update" | "delete">("create");
  const [fields, setFields] = useState<PolicyFields>({
    principal: "",
    mountId: null,
    prefix: "",
    effect: "allow",
    actions: ["list"],
  });
  const [impact, setImpact] = useState<ImpactSnapshot | null>(null),
    [aliasAck, setAliasAck] = useState(false),
    [configAck, setConfigAck] = useState(false),
    [confirm, setConfirm] = useState(""),
    [result, setResult] = useState("");
  const clear = () => {
    setImpact(null);
    setAliasAck(false);
    setConfigAck(false);
    setConfirm("");
    setResult("");
  };
  const clearAuthorization = () => {
    clear();
    setEditing(null);
    setMode("create");
    setFields({
      principal: "",
      mountId: null,
      prefix: "",
      effect: "allow",
      actions: ["list"],
    });
  };
  const list = usePage<Policy>("/api/kv/policies", true, clearAuthorization),
    task = useTask(clearAuthorization);
  useEffect(() => {
    if (task.error) {
      setImpact(null);
      setAliasAck(false);
      setConfigAck(false);
      setConfirm("");
    }
  }, [task.error]);
  const update = (value: Partial<PolicyFields>) => {
    setFields({ ...fields, ...value });
    clear();
  };
  const select = (policy: Policy, action: "update" | "delete") => {
    setEditing(policy);
    setMode(action);
    setFields({
      principal: policy.principal,
      mountId: policy.mountId,
      prefix: policy.prefix,
      effect: policy.effect,
      actions: [...policy.actions],
    });
    clear();
  };
  const expected = policyConfirmation(editing ?? fields);
  const preview = (cursor?: string) => {
    const input =
      mode === "delete"
        ? { action: mode, id: editing!.id, revision: editing!.revision }
        : {
            action: mode,
            ...fields,
            ...(editing ? { id: editing.id, revision: editing.revision } : {}),
          };
    void task.run(
      (request) =>
        request<ImpactPage>("/api/kv/policies/preview", "POST", {
          ...input,
          ...(cursor ? { cursor } : {}),
        }),
      (page) => setImpact(appendImpact(cursor ? impact : null, page)),
    );
  };
  const commit = () => {
    void task.run(
      async (request) => {
        if (confirm !== expected)
          throw new AdminInputError("Type the exact policy confirmation.");
        const legacyImpact = impactAcknowledgement(impact, aliasAck, configAck);
        return request<Policy | { success: boolean }>(
          editing ? `/api/kv/policies/${editing.id}` : "/api/kv/policies",
          mode === "delete" ? "DELETE" : editing ? "PATCH" : "POST",
          {
            ...(mode === "delete" ? {} : fields),
            ...(editing ? { revision: editing.revision } : {}),
            ...(legacyImpact ? { legacyImpact } : {}),
          },
        );
      },
      () => {
        clear();
        setEditing(null);
        setMode("create");
        setResult(
          `Policy ${mode} committed. Refresh capabilities before using data actions.`,
        );
        list.refresh();
        changed("policies");
      },
    );
  };
  return (
    <fieldset
      disabled={task.busy}
      aria-label="Policies administration"
      className="space-y-4"
    >
      <p className="text-sm text-zinc-400">
        Deny overrides allow. Prefixes match full path segments; an empty prefix
        covers the mount root. Engine administration never bypasses KV data
        denies.
      </p>
      {list.controls}
      <TaskState task={list.task} />
      {list.page && (
        <Table
          headings={[
            "Principal / rule",
            "Scope / operations",
            "Revision / actions",
          ]}
        >
          {list.page.items.map((policy) => (
            <tr key={policy.id}>
              <td className="break-all">
                {policy.principal}
                <br />
                <span className="text-xs text-zinc-400">{policy.id}</span>
              </td>
              <td className="break-all">
                {policy.effect} · {policy.mountId ?? "all mounts"}/
                {policy.prefix || "(root)"}
                <br />
                {policy.actions.join(", ")}
              </td>
              <td>
                {policy.revision}
                <div className="flex gap-2">
                  <Button
                    disabled={task.busy}
                    onClick={() => select(policy, "update")}
                  >
                    Edit
                  </Button>
                  <Button
                    danger
                    disabled={task.busy}
                    onClick={() => select(policy, "delete")}
                  >
                    Remove
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </Table>
      )}
      <div className={boxClass}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">
            {mode === "delete"
              ? "Remove captured policy"
              : editing
                ? "Edit captured policy"
                : "Create scoped policy"}
          </h3>
          <Button
            disabled={task.busy}
            onClick={() => {
              setEditing(null);
              setMode("create");
              clear();
              setFields({
                principal: "",
                mountId: null,
                prefix: "",
                effect: "allow",
                actions: ["list"],
              });
            }}
          >
            New rule
          </Button>
        </div>
        {mode !== "delete" && (
          <>
            <Field
              label="Exact principal"
              hint="user:<user ID>, identity:<identity UUID>, or legacy-lookup. Legacy policies accept list/read only."
            >
              <input
                className={inputClass}
                value={fields.principal}
                onChange={(event) => update({ principal: event.target.value })}
              />
            </Field>
            <Check
              label="Apply this rule to all mounts"
              checked={fields.mountId === null}
              onChange={(checked) => update({ mountId: checked ? null : "" })}
            />
            {fields.mountId !== null && (
              <Field label="Mount UUID">
                <input
                  className={inputClass}
                  value={fields.mountId}
                  onChange={(event) => update({ mountId: event.target.value })}
                />
              </Field>
            )}
            <Field label="Path prefix (empty means root)">
              <input
                className={inputClass}
                value={fields.prefix}
                onChange={(event) => update({ prefix: event.target.value })}
              />
            </Field>
            <Field label="Effect">
              <select
                className={inputClass}
                value={fields.effect}
                onChange={(event) =>
                  update({ effect: event.target.value as "allow" | "deny" })
                }
              >
                <option value="allow">Allow</option>
                <option value="deny">Deny</option>
              </select>
            </Field>
            <Actions
              value={fields.actions}
              onChange={(actions) => update({ actions })}
            />
          </>
        )}
        <Button
          disabled={task.busy}
          onClick={() => {
            clear();
            preview();
          }}
        >
          Capture access impact preview
        </Button>
        {impact && (
          <Impact
            snapshot={impact}
            busy={task.busy}
            next={() => preview(impact.page.nextCursor ?? undefined)}
            aliasesChecked={aliasAck}
            setAliasesChecked={setAliasAck}
            configurationChecked={configAck}
            setConfigurationChecked={setConfigAck}
          />
        )}
        <Exact expected={expected} value={confirm} onChange={setConfirm} />
        <Button
          danger={mode === "delete"}
          disabled={
            task.busy ||
            !impact?.complete ||
            confirm !== expected ||
            (impact.page.required &&
              (!aliasAck ||
                (!!impact.page.nonsecretConfigurationAffected && !configAck)))
          }
          onClick={commit}
        >
          Commit policy {mode}
        </Button>
        <TaskState task={task} />
        {result && (
          <p role="status" className="text-sm text-indigo-200">
            {result}
          </p>
        )}
      </div>
    </fieldset>
  );
}

function Identities({ changed }: { changed: Changed }) {
  const [credential, setCredential] = useState<string | null>(null),
    [issuedId, setIssuedId] = useState("");
  const [owner, setOwner] = useState(""),
    [name, setName] = useState(""),
    [expiry, setExpiry] = useState(""),
    [scopes, setScopes] = useState<IdentityScope[]>([
      { mountId: "", prefix: "", actions: ["list"] },
    ]);
  const [selected, setSelected] = useState<Identity | null>(null),
    [confirm, setConfirm] = useState(""),
    [issueAck, setIssueAck] = useState(false),
    [result, setResult] = useState("");
  const clearAuthorization = () => {
    setCredential(null);
    setIssuedId("");
    setOwner("");
    setName("");
    setExpiry("");
    setScopes([{ mountId: "", prefix: "", actions: ["list"] }]);
    setSelected(null);
    setConfirm("");
    setIssueAck(false);
    setResult("");
  };
  const list = usePage<Identity>("/api/kv/identities", true, clearAuthorization),
    task = useTask(clearAuthorization);
  useEffect(() => {
    if (task.error || list.task.error) {
      setCredential(null);
      setIssuedId("");
      setIssueAck(false);
      setConfirm("");
    }
  }, [task.error, list.task.error]);
  const editScope = (index: number, value: Partial<IdentityScope>) => {
    setCredential(null);
    setIssueAck(false);
    setScopes(
      scopes.map((scope, i) => (i === index ? { ...scope, ...value } : scope)),
    );
  };
  const issue = () => {
    setCredential(null);
    setIssuedId("");
    void task.run(
      async (request) => {
        if (
          !issueAck ||
          !owner ||
          !/^[A-Za-z0-9._-]{1,64}$/.test(name) ||
          !expiry ||
          scopes.some(
            (scope) => !isUuid(scope.mountId) || !scope.actions.length,
          )
        )
          throw new AdminInputError(
            "Enter an exact owner, valid name, explicit mount scopes and expiry, then acknowledge issuance.",
          );
        const expiresAt = new Date(expiry);
        if (
          !Number.isFinite(expiresAt.getTime()) ||
          expiresAt.getTime() <= Date.now() ||
          expiresAt.getTime() > Date.now() + 30 * 86400000
        )
          throw new AdminInputError("Choose an expiry in the next 30 days.");
        return request<Identity & { credential: string }>(
          "/api/kv/identities",
          "POST",
          { ownerId: owner, name, expiresAt: expiresAt.toISOString(), scopes },
        );
      },
      (data) => {
        setCredential(data.credential);
        setIssuedId(data.id);
        setIssueAck(false);
        setResult(
          "Identity issued. The token is displayed once in this panel.",
        );
        list.refresh();
        changed("identities");
      },
    );
  };
  const revoke = () => {
    if (!selected) return;
    setCredential(null);
    void task.run(
      async (request) => {
        if (confirm !== identityConfirmation(selected))
          throw new AdminInputError(
            "Confirm the exact captured identity and expiry.",
          );
        return request(`/api/kv/identities/${selected.id}`, "DELETE");
      },
      () => {
        setSelected(null);
        setConfirm("");
        setResult(
          "The selected identity is revoked. New operations are denied by fresh server checks.",
        );
        list.refresh();
        changed("identities");
      },
    );
  };
  return (
    <fieldset
      disabled={task.busy}
      aria-label="Identities administration"
      className="space-y-4"
    >
      <p className="text-sm text-zinc-400">
        Tokens authenticate only /api/kv/automation. Effective access is the
        intersection of token scopes and the owner’s current role, session and
        policy. Tokens never inherit engine administration. Owner reset,
        deletion or demotion can revoke access before expiry.
      </p>
      {list.controls}
      <TaskState task={list.task} />
      {list.page && (
        <Table headings={["Identity / owner", "Expiry / state", "Action"]}>
          {list.page.items.map((identity) => (
            <tr key={identity.id}>
              <td className="break-all">
                {identity.name}
                <br />
                <span className="text-xs text-zinc-400">
                  {identity.id}
                  <br />
                  owner {identity.ownerId}
                </span>
              </td>
              <td className="break-all">
                {identity.expiresAt}
                <br />
                {identity.revokedAt
                  ? `Revoked ${identity.revokedAt}`
                  : Date.parse(identity.expiresAt) <= Date.now()
                    ? "Expired"
                    : "Active at capture"}
              </td>
              <td>
                <Button
                  danger
                  disabled={task.busy || !!identity.revokedAt}
                  onClick={() => {
                    setCredential(null);
                    setSelected(identity);
                    setConfirm("");
                  }}
                >
                  Revoke identity
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
      {selected && (
        <div className={boxClass}>
          <p className="text-xs text-zinc-400">
            This API has no identity revision/CAS parameter. Revocation targets
            the exact immutable identity ID with fresh server authorization.
          </p>
          <Exact
            expected={identityConfirmation(selected)}
            value={confirm}
            onChange={setConfirm}
          />
          <Button
            danger
            disabled={task.busy || confirm !== identityConfirmation(selected)}
            onClick={revoke}
          >
            Confirm revocation
          </Button>
          <Button
            disabled={task.busy}
            onClick={() => {
              setSelected(null);
              setConfirm("");
            }}
          >
            Cancel revocation
          </Button>
        </div>
      )}
      <div className={boxClass}>
        <h3 className="font-medium">Issue expiring automation identity</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Exact owner user ID">
            <input
              className={inputClass}
              value={owner}
              onChange={(event) => {
                setOwner(event.target.value);
                setIssueAck(false);
                setCredential(null);
              }}
            />
          </Field>
          <Field label="Identity name">
            <input
              className={inputClass}
              maxLength={64}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setIssueAck(false);
                setCredential(null);
              }}
            />
          </Field>
          <Field label="Expiry (your browser’s local time, at most 30 days)">
            <input
              className={inputClass}
              type="datetime-local"
              value={expiry}
              onChange={(event) => {
                setExpiry(event.target.value);
                setIssueAck(false);
                setCredential(null);
              }}
            />
          </Field>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Expiry presets">
          {[
            [1, "1 hour"],
            [24, "1 day"],
            [168, "7 days"],
            [720, "30 days"],
          ].map(([hours, label]) => (
            <Button
              key={hours}
              disabled={task.busy}
              onClick={() => {
                const date = new Date(Date.now() + Number(hours) * 3600000),
                  pad = (value: number) => String(value).padStart(2, "0");
                setExpiry(
                  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`,
                );
                setIssueAck(false);
                setCredential(null);
              }}
            >
              Expire in {label}
            </Button>
          ))}
        </div>
        {scopes.map((scope, index) => (
          <fieldset
            key={index}
            className="space-y-3 rounded border border-zinc-800 p-3"
          >
            <legend className="text-sm">Scope {index + 1}</legend>
            <Field label={`Scope ${index + 1} mount UUID`}>
              <input
                className={inputClass}
                value={scope.mountId}
                onChange={(event) =>
                  editScope(index, { mountId: event.target.value })
                }
              />
            </Field>
            <Field label={`Scope ${index + 1} path prefix`}>
              <input
                className={inputClass}
                value={scope.prefix}
                onChange={(event) =>
                  editScope(index, { prefix: event.target.value })
                }
              />
            </Field>
            <Actions
              value={scope.actions}
              onChange={(actions) => editScope(index, { actions })}
            />
            <Button
              disabled={scopes.length === 1 || task.busy}
              onClick={() => {
                setScopes(scopes.filter((_, i) => i !== index));
                setIssueAck(false);
                setCredential(null);
              }}
            >
              Remove scope
            </Button>
          </fieldset>
        ))}
        <Button
          disabled={task.busy || scopes.length >= 32}
          onClick={() => {
            setScopes([
              ...scopes,
              { mountId: "", prefix: "", actions: ["list"] },
            ]);
            setIssueAck(false);
            setCredential(null);
          }}
        >
          Add scope
        </Button>
        <Check
          label={`Issue one token for owner ${owner || "(choose owner)"} with the ${scopes.length} displayed scopes and expiry ${expiry || "(choose expiry)"}. I will save it securely before closing.`}
          checked={issueAck}
          onChange={setIssueAck}
        />
        <Button
          disabled={task.busy || !issueAck || !!credential}
          onClick={issue}
        >
          Issue token once
        </Button>
        {credential && (
          <div className="space-y-3 rounded border border-indigo-700 bg-indigo-950/30 p-3">
            <p className="break-all text-sm text-indigo-200">
              One-time token for {issuedId}. It will disappear on close,
              navigation, permission loss or hiding this page.
            </p>
            <Field label="One-time automation token">
              <textarea
                className={inputClass + " break-all font-mono"}
                rows={4}
                readOnly
                autoComplete="off"
                spellCheck={false}
                value={credential}
              />
            </Field>
            <Button
              onClick={() => {
                setCredential(null);
                setIssuedId("");
                setResult(
                  "Token display cleared. It cannot be retrieved again; revoke the identity if it was not saved.",
                );
              }}
            >
              Clear token display
            </Button>
          </div>
        )}
        <TaskState task={task} />
        {result && (
          <p role="status" className="text-sm text-indigo-200">
            {result}
          </p>
        )}
      </div>
    </fieldset>
  );
}

function AuditView({ pathId }: { pathId: string | null }) {
  const [pathFilter, setPathFilter] = useState(pathId ?? ""),
    [operationFilter, setOperationFilter] = useState(""),
    [filters, setFilters] = useState<string | null>(
      pathId ? `?pathId=${encodeURIComponent(pathId)}` : "",
    ),
    [validation, setValidation] = useState("");
  const clearAudit = useCallback(() => {
    setPathFilter("");
    setOperationFilter("");
    setFilters(null);
    setValidation("");
  }, []);
  const list = usePage<Audit>(
    filters === null ? null : "/api/kv/audit" + filters,
    false,
    clearAudit,
  );
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400">
        Redacted authorization and operation metadata, at most 100 records per
        page. “Authorized” records an access decision and does not prove
        delivery. Scoped users see only permitted path metadata.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Path UUID filter">
          <input
            className={inputClass}
            value={pathFilter}
            onChange={(event) => setPathFilter(event.target.value)}
          />
        </Field>
        <Field label="Operation UUID filter">
          <input
            className={inputClass}
            value={operationFilter}
            onChange={(event) => setOperationFilter(event.target.value)}
          />
        </Field>
      </div>
      <Button
        disabled={list.task.busy}
        onClick={() => {
          if (
            (pathFilter && !isUuid(pathFilter)) ||
            (operationFilter && !isUuid(operationFilter))
          ) {
            setValidation("Filters require exact UUIDs.");
            return;
          }
          setValidation("");
          const query = new URLSearchParams();
          if (pathFilter) query.set("pathId", pathFilter);
          if (operationFilter) query.set("operationId", operationFilter);
          setFilters(query.size ? "?" + query.toString() : "");
        }}
      >
        Apply audit filters
      </Button>
      {validation && (
        <p role="alert" className="text-sm text-rose-300">
          {validation}
        </p>
      )}
      {list.controls}
      <TaskState task={list.task} />
      {list.page && (
        <>
          <p className="text-xs text-zinc-400">
            {list.page.items.length} records on this page.
            {!list.page.items.length && list.page.nextCursor
              ? " Filtered pages can be empty; continue to the next cursor."
              : ""}
          </p>
          <Table
            headings={[
              "Time / actor",
              "Action / outcome",
              "Exact metadata target",
              "Version / operation",
            ]}
          >
            {list.page.items.map((row) => (
              <tr key={row.id}>
                <td className="break-all">
                  {row.createdAt}
                  <br />
                  <span className="text-xs text-zinc-400">{row.actorId}</span>
                </td>
                <td>
                  {row.action}
                  <br />
                  {row.outcome}
                </td>
                <td className="break-all">
                  {row.path ?? "Administrative metadata"}
                  <br />
                  {row.namespace && `${row.namespace}/${row.name ?? ""}`}
                  <br />
                  {row.principal}
                  {row.alias && (
                    <>
                      <br />
                      alias {row.alias} · key {row.key}
                    </>
                  )}
                </td>
                <td className="break-all">
                  {row.previousVersion ?? "—"} → {row.newVersion ?? "—"}
                  <br />
                  <span className="text-xs text-zinc-400">
                    {row.operationId ?? "—"}
                  </span>
                </td>
              </tr>
            ))}
          </Table>
        </>
      )}
    </div>
  );
}

function Legacy({
  pathId,
  changed,
}: {
  pathId: string | null;
  changed: Changed;
}) {
  const [principal, setPrincipal] = useState<LegacyPrincipal | null>(null),
    [alias, setAlias] = useState(""),
    [change, setChange] = useState<Record<string, unknown> | null>(null);
  const [impact, setImpact] = useState<ImpactSnapshot | null>(null),
    [aliasAck, setAliasAck] = useState(false),
    [configAck, setConfigAck] = useState(false),
    [confirm, setConfirm] = useState(""),
    [expected, setExpected] = useState(""),
    [result, setResult] = useState("");
  const clear = () => {
    setChange(null);
    setImpact(null);
    setAliasAck(false);
    setConfigAck(false);
    setConfirm("");
    setExpected("");
  };
  const clearAuthorization = () => {
    clear();
    setPrincipal(null);
    setAlias("");
    setResult("");
  };
  const list = usePage<Grant>("/api/kv/legacy/grants", true, clearAuthorization),
    task = useTask(clearAuthorization);
  useEffect(() => {
    if (task.error) {
      setImpact(null);
      setAliasAck(false);
      setConfigAck(false);
      setConfirm("");
    }
  }, [task.error]);
  const { run } = task;
  const load = useCallback(() => {
    setPrincipal(null);
    void run(
      (request) => request<LegacyPrincipal>("/api/kv/legacy"),
      setPrincipal,
    );
  }, [run]);
  useEffect(() => {
    load();
  }, [load]);
  const preview = (
    input: Record<string, unknown>,
    confirmation: string,
    cursor?: string,
  ) => {
    if (!cursor) clear();
    void task.run(
      (request) =>
        request<ImpactPage>("/api/kv/legacy/preview", "POST", {
          ...input,
          ...(cursor ? { cursor } : {}),
        }),
      (page) => {
        setChange(input);
        setExpected(confirmation);
        setImpact(appendImpact(cursor ? impact : null, page));
      },
    );
  };
  const grant = () => {
    if (!principal || !pathId) return;
    clear();
    void task.run(
      async (request) => {
        const path = await request<PathMetadata>(route(pathId));
        const input = {
          kind: "grant",
          pathId,
          pathRevision: path.revision,
          alias,
          revision: principal.revision,
        };
        const page = await request<ImpactPage>(
          "/api/kv/legacy/preview",
          "POST",
          input,
        );
        return { path, input, page };
      },
      (data) => {
        setChange(data.input);
        setImpact(appendImpact(null, data.page));
        setExpected(
          `grant ${alias} path=${pathId} target=${data.path.namespace}/${data.path.name} pathRevision=${data.path.revision} principalRevision=${principal.revision}`,
        );
      },
    );
  };
  const commit = () => {
    if (!change) return;
    void task.run(
      async (request) => {
        if (confirm !== expected)
          throw new AdminInputError(
            "Type the exact captured legacy change confirmation.",
          );
        const legacyImpact = impactAcknowledgement(impact, aliasAck, configAck),
          { kind, grantId, ...body } = change;
        return request(
          kind === "principal"
            ? "/api/kv/legacy"
            : kind === "grant"
              ? "/api/kv/legacy/grants"
              : `/api/kv/legacy/grants/${grantId}`,
          kind === "principal" ? "PATCH" : kind === "grant" ? "POST" : "DELETE",
          { ...body, legacyImpact },
        );
      },
      () => {
        clear();
        setResult(
          "The exact legacy authorization change committed. Native ownership and lookup availability remain separate checks.",
        );
        queueMicrotask(load);
        list.refresh();
        changed("legacy");
      },
    );
  };
  return (
    <fieldset
      disabled={task.busy}
      aria-label="Legacy administration"
      className="space-y-4"
    >
      <p className="text-sm text-zinc-400">
        The legacy principal controls current exact-alias lookup and nonsecret
        configuration. It has no KV administration, historic value or
        automation-token audience. Previews never reveal native values.
      </p>
      <div className={boxClass}>
        <h3 className="font-medium">Legacy lookup principal</h3>
        {principal ? (
          <>
            <p className="text-sm">
              legacy-lookup · {principal.enabled ? "Enabled" : "Disabled"} ·
              revision {principal.revision} · {principal.grantCount} grants
            </p>
            <Button
              disabled={task.busy}
              onClick={() =>
                preview(
                  {
                    kind: "principal",
                    enabled: !principal.enabled,
                    revision: principal.revision,
                  },
                  `legacy-lookup revision=${principal.revision} enabled=${!principal.enabled}`,
                )
              }
            >
              Preview {principal.enabled ? "disable" : "enable"} impact
            </Button>
          </>
        ) : (
          <p className="text-sm text-zinc-400">
            Principal metadata unavailable or loading.
          </p>
        )}
        <Button
          disabled={task.busy}
          onClick={() => {
            clear();
            load();
          }}
        >
          Refresh principal
        </Button>
      </div>
      {list.controls}
      <TaskState task={list.task} />
      {list.page && (
        <Table headings={["Exact alias / target", "Path / grant", "Action"]}>
          {list.page.items.map((row) => (
            <tr key={row.id}>
              <td className="break-all">
                {row.alias}
                <br />
                <span className="text-xs text-zinc-400">
                  {row.namespace}/{row.name}/{row.key}
                </span>
              </td>
              <td className="break-all text-xs">
                {row.pathId}
                <br />
                {row.id}
              </td>
              <td>
                <Button
                  danger
                  disabled={!principal || task.busy}
                  onClick={() =>
                    preview(
                      {
                        kind: "revoke",
                        grantId: row.id,
                        revision: principal!.revision,
                      },
                      `revoke ${row.id} alias=${row.alias} target=${row.namespace}/${row.name}/${row.key} principalRevision=${principal!.revision}`,
                    )
                  }
                >
                  Preview revoke
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
      <div className={boxClass}>
        <h3 className="font-medium">Grant / restore exact alias access</h3>
        <p className="break-all text-xs text-zinc-400">
          Selected registered path: {pathId ?? "choose a path UUID above"}. The
          preview validates the exact mapped key and a previously committed
          path.
        </p>
        <Field label="Exact existing alias">
          <input
            className={inputClass}
            value={alias}
            onChange={(event) => {
              setAlias(event.target.value);
              clear();
            }}
          />
        </Field>
        <Button
          disabled={task.busy || !principal || !pathId || !alias}
          onClick={grant}
        >
          Preview exact grant
        </Button>
      </div>
      {impact && change && (
        <div className={boxClass}>
          <Impact
            snapshot={impact}
            busy={task.busy}
            next={() =>
              preview(change, expected, impact.page.nextCursor ?? undefined)
            }
            aliasesChecked={aliasAck}
            setAliasesChecked={setAliasAck}
            configurationChecked={configAck}
            setConfigurationChecked={setConfigAck}
          />
          <Exact expected={expected} value={confirm} onChange={setConfirm} />
          <Button
            danger
            disabled={
              task.busy ||
              !impact.complete ||
              !aliasAck ||
              (!!impact.page.nonsecretConfigurationAffected && !configAck) ||
              confirm !== expected
            }
            onClick={commit}
          >
            Commit captured legacy change
          </Button>
          <Button disabled={task.busy} onClick={clear}>
            Cancel preview
          </Button>
        </div>
      )}
      <TaskState task={task} />
      {result && (
        <p role="status" className="text-sm text-indigo-200">
          {result}
        </p>
      )}
    </fieldset>
  );
}

async function capturePath(
  request: Request,
  pathId: string,
): Promise<PathSnapshot> {
  const [path, capabilities, status, versions] = await Promise.all([
    request<PathMetadata>(route(pathId)),
    request<Capabilities>(route(pathId) + "/capabilities"),
    request<NativeStatus>(route(pathId) + "/status"),
    request<Versions>(route(pathId) + "/versions"),
  ]);
  if (
    path.id !== pathId ||
    capabilities.pathId !== pathId ||
    status.pathId !== pathId ||
    versions.pathId !== pathId ||
    capabilities.revision !== path.revision ||
    !status.uid || versions.uid !== status.uid ||
    versions.head !== status.head ||
    versions.resourceVersion !== status.resourceVersion
  )
    throw new AdminInputError(
      "Path metadata changed during capture. Refresh before confirming an action.",
    );
  return { path, capabilities, status, versions };
}
function PathIdentity({ snapshot }: { snapshot: PathSnapshot }) {
  return (
    <div className="space-y-2 text-sm">
      <p className="break-all text-indigo-200">
        {snapshot.path.path} · {snapshot.path.namespace}/{snapshot.path.name}
      </p>
      <p className="break-all text-xs text-zinc-400">
        Captured path {snapshot.path.id}, revision {snapshot.path.revision};
        head {snapshot.status.head}; canonical UID {snapshot.status.uid}; native resourceVersion{" "}
        {snapshot.status.resourceVersion};{" "}
        {snapshot.status.tombstone ? "tombstoned" : "active"};{" "}
        {snapshot.status.adopted ? "adopted" : "not adopted"}. Canonical and selected history
        identities are captured explicitly; ownership and delete preconditions remain server checks.
      </p>
      <p className="text-xs text-zinc-400">
        Native changes:{" "}
        {snapshot.capabilities.nativeMutationEnabled
          ? "enabled by operator assertion"
          : "disabled"}
        . This flag does not prove external RBAC or admission guards.
      </p>
    </div>
  );
}
function Cleanup({ result }: { result: CleanupResult }) {
  return (
    <div className="space-y-2">
      <p role="status" className="break-all text-sm text-amber-200">
        Reference operation {result.operationId}: {result.outcome}. History
        cleanup{" "}
        {result.cleanupComplete
          ? "complete"
          : "partial; retained or uncertain items need inspection"}
        . Head {result.head}; resourceVersion {result.resourceVersion}.
      </p>
      <Table headings={["History / version", "Outcome", "HTTP status"]}>
        {result.cleanup.map((row) => (
          <tr key={row.name}>
            <td className="break-all">
              {row.name}
              <br />
              version {row.version ?? "—"}
            </td>
            <td>{row.outcome}</td>
            <td>{row.status}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
function NativeAdministration({
  pathId,
  rotation,
  changed,
}: {
  pathId: string;
  rotation: boolean;
  changed: Changed;
}) {
  const task = useTask(),
    [snapshot, setSnapshot] = useState<PathSnapshot | null>(null),
    [epoch, setEpoch] = useState(0);
  const { run } = task;
  const capture = useCallback(() => {
    setSnapshot(null);
    void run(
      (request) => capturePath(request, pathId),
      (result) => {
        setSnapshot(result);
        setEpoch((value) => value + 1);
      },
    );
  }, [pathId, run]);
  useEffect(() => {
    capture();
  }, [capture]);
  return (
    <div className="space-y-4">
      <Button disabled={task.busy} onClick={capture}>
        Capture fresh path metadata
      </Button>
      <TaskState task={task} />
      {snapshot && (
        <>
          <PathIdentity snapshot={snapshot} />
          {rotation ? (
            <Rotations key={epoch} snapshot={snapshot} changed={changed} />
          ) : (
            <History key={epoch} snapshot={snapshot} changed={changed} />
          )}
        </>
      )}
    </div>
  );
}
function History({
  snapshot,
  changed,
}: {
  snapshot: PathSnapshot;
  changed: Changed;
}) {
  const task = useTask(),
    [retention, setRetention] = useState(String(snapshot.path.retention)),
    [retentionConfirm, setRetentionConfirm] = useState(""),
    [selected, setSelected] = useState<number[]>([]),
    [destroyConfirm, setDestroyConfirm] = useState("");
  const [gc, setGc] = useState<GcPreview | null>(null),
    [gcSelections, setGcSelections] = useState<string[]>([]),
    [gcConfirm, setGcConfirm] = useState(""),
    [cleanup, setCleanup] = useState<CleanupResult | null>(null),
    [finished, setFinished] = useState(false),
    [message, setMessage] = useState("");
  const [operationId, setOperationId] = useState(""),
    [operationConfirm, setOperationConfirm] = useState(""),
    [operation, setOperation] = useState<Operation | null>(null);
  useEffect(() => {
    if (task.error) {
      setFinished(true);
      setDestroyConfirm("");
      setGcConfirm("");
      setRetentionConfirm("");
    }
  }, [task.error]);
  const expected = pathConfirmation(snapshot);
  const minimum = 1; // Existing route enforces 1..operator-configured maximum (never greater than 100).
  const destroy = () => {
    void task.run(
      (request) =>
        request<CleanupResult>(
          route(snapshot.path.id) + "/destroy",
          "POST",
          destroyBody(snapshot, selected, destroyConfirm),
        ),
      (result) => {
        setCleanup(result);
        setFinished(true);
        setSelected([]);
        setDestroyConfirm("");
        changed("history");
      },
    );
  };
  const previewGc = () => {
    setGc(null);
    setGcSelections([]);
    setGcConfirm("");
    void task.run(
      (request) =>
        request<GcPreview>("/api/kv/history/gc/preview", "POST", {
          pathId: snapshot.path.id,
        }),
      (result) => {
        if (result.items.length > 100)
          throw new AdminInputError("Cleanup preview exceeds 100 candidates.");
        setGc(result);
      },
    );
  };
  const commitGc = () => {
    if (!gc) return;
    void task.run(
      (request) =>
        request<CleanupResult>(
          "/api/kv/history/gc",
          "POST",
          gcBody(
            snapshot,
            gc,
            gc.items.filter((row) =>
              gcSelections.includes(historyConfirmation(row)),
            ),
            gcConfirm,
          ),
        ),
      (result) => {
        setCleanup(result);
        setFinished(true);
        setGc(null);
        setGcSelections([]);
        setGcConfirm("");
        changed("history");
      },
    );
  };
  return (
    <fieldset
      disabled={task.busy}
      aria-label="History administration"
      className="min-w-0 space-y-4"
    >
      <div className={boxClass}>
        <h3 className="font-medium">Committed-version retention</h3>
        <p className="text-xs text-zinc-400">
          Minimum {minimum}; operator-configured maximum at most 100. Changing
          the limit does not delete objects immediately. Future native commits
          prune references; aged orphan cleanup remains explicit.
        </p>
        <Field label="Retention limit">
          <input
            className={inputClass}
            type="number"
            min={minimum}
            max={100}
            value={retention}
            onChange={(event) => {
              setRetention(event.target.value);
              setRetentionConfirm("");
            }}
          />
        </Field>
        <Exact
          expected={`retention ${snapshot.path.id} revision=${snapshot.path.revision} limit=${retention}`}
          value={retentionConfirm}
          onChange={setRetentionConfirm}
        />
        <Button
          disabled={
            task.busy ||
            finished ||
            !canAct(snapshot, "update", false) ||
            !Number.isInteger(Number(retention)) ||
            Number(retention) < minimum ||
            Number(retention) > 100 ||
            Number(retention) === snapshot.path.retention ||
            retentionConfirm !==
              `retention ${snapshot.path.id} revision=${snapshot.path.revision} limit=${retention}`
          }
          onClick={() => {
            void task.run(
              (request) =>
                request(route(snapshot.path.id), "PATCH", {
                  revision: snapshot.path.revision,
                  retention: Number(retention),
                }),
              () => {
                setFinished(true);
                setMessage(
                  "Retention metadata committed. Capture fresh path metadata before another action.",
                );
                changed("paths");
              },
            );
          }}
        >
          Commit retention revision
        </Button>
      </div>
      <div className={boxClass}>
        <h3 className="font-medium">Permanently destroy committed versions</h3>
        <p className="text-xs text-zinc-400">
          Select up to 100 committed versions. The active head requires a prior
          tombstone. The canonical Secret, unrelated keys and monotonic version
          sequence are preserved. Reference CAS and per-item deletion outcomes
          are separate.
        </p>
        {snapshot.versions.items.length ? (
          <div className="max-h-72 space-y-2 overflow-y-auto">
            {snapshot.versions.items.map((row) => (
              <Check
                key={row.version}
                label={`Version ${row.version} · ${row.name} · UID ${row.uid} · ${row.createdAt} · ${row.tombstone ? "tombstone" : "value snapshot"}${row.version === snapshot.status.head ? " · current head" : ""}`}
                disabled={
                  finished ||
                  (row.version === snapshot.status.head &&
                    !snapshot.status.tombstone)
                }
                checked={selected.includes(row.version)}
                onChange={(checked) => {
                  setSelected(
                    checked
                      ? [...selected, row.version]
                      : selected.filter((value) => value !== row.version),
                  );
                  setDestroyConfirm("");
                }}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-zinc-400">
            No committed versions in this snapshot.
          </p>
        )}
        <Exact
          expected={expected}
          value={destroyConfirm}
          onChange={setDestroyConfirm}
        />
        <p className="text-xs text-zinc-400">
          Selected versions: {selected.join(", ") || "none"}
        </p>
        <Button
          danger
          disabled={
            task.busy ||
            finished ||
            !canAct(snapshot, "destroy") ||
            !selected.length ||
            destroyConfirm !== expected
          }
          onClick={destroy}
        >
          Destroy selected versions once
        </Button>
      </div>
      <div className={boxClass}>
        <h3 className="font-medium">Aged orphan history cleanup</h3>
        <p className="text-xs text-zinc-400">
          Administrator plus destroy policy. Preview lists metadata only; commit
          rechecks immutable ownership, recorded operation, 24-hour minimum age,
          all source references and exact UID/resourceVersion, then CAS-fences
          the source. There is no background sweep.
        </p>
        <Button
          disabled={
            task.busy || finished || !canAct(snapshot, "destroy", false)
          }
          onClick={previewGc}
        >
          Preview aged orphan GC
        </Button>
        {gc && (
          <>
            <p className="text-sm">
              {gc.eligible} eligible; {gc.retained} retained. Minimum age{" "}
              {gc.minimumAgeHours} hours.{" "}
              {gc.complete
                ? "All candidates fit this preview."
                : "First 100 candidates shown; later batches require a new preview after inspection."}
            </p>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {gc.items.map((row) => (
                <Check
                  key={row.name}
                  label={historyConfirmation(row)}
                  checked={gcSelections.includes(historyConfirmation(row))}
                  onChange={(checked) => {
                    const value = historyConfirmation(row);
                    setGcSelections(
                      checked
                        ? [...gcSelections, value]
                        : gcSelections.filter((item) => item !== value),
                    );
                    setGcConfirm("");
                  }}
                />
              ))}
            </div>
            <Exact
              expected={expected}
              value={gcConfirm}
              onChange={setGcConfirm}
            />
            <Button
              danger
              disabled={
                task.busy ||
                finished ||
                !canAct(snapshot, "destroy") ||
                !gcSelections.length ||
                gcConfirm !== expected
              }
              onClick={commitGc}
            >
              Delete exactly selected orphan histories
            </Button>
          </>
        )}
      </div>
      <div className={boxClass}>
        <h3 className="font-medium">Inspect ambiguous operation / recovery</h3>
        <p className="text-xs text-zinc-400">
          Resolution checks positive native metadata proof. Missing or pruned
          proof stays ambiguous; it never regenerates values, retries a native
          write or deletes history. This inspection may reconcile the
          operation’s metadata outcome.
        </p>
        <Field label="Exact operation UUID">
          <input
            className={inputClass}
            value={operationId}
            onChange={(event) => {
              setOperationId(event.target.value);
              setOperationConfirm("");
              setOperation(null);
            }}
          />
        </Field>
        <Exact
          expected={`inspect operation ${operationId}`}
          value={operationConfirm}
          onChange={setOperationConfirm}
        />
        <Button
          disabled={
            task.busy ||
            !isUuid(operationId) ||
            operationConfirm !== `inspect operation ${operationId}`
          }
          onClick={() => {
            void task.run(
              (request) =>
                request<Operation>(`/api/kv/operations/${operationId}`),
              (result) => {
                setOperation(result);
                changed("recovery");
              },
            );
          }}
        >
          Inspect operation metadata
        </Button>
        {operation && (
          <dl className="space-y-1 break-all text-sm">
            <dt>Operation / outcome</dt>
            <dd>
              {operation.id} · {operation.outcome}
            </dd>
            <dt>Exact target / action</dt>
            <dd>
              {operation.pathId} · {operation.namespace}/{operation.name} ·{" "}
              {operation.path} · {operation.action}
            </dd>
            <dt>Versions</dt>
            <dd>
              {operation.previousVersion ?? "—"} → {operation.newVersion ?? "—"}
            </dd>
          </dl>
        )}
      </div>
      <TaskState task={task} />
      {message && (
        <p role="status" className="text-sm text-indigo-200">
          {message}
        </p>
      )}
      {cleanup && <Cleanup result={cleanup} />}
      {finished && (
        <p className="text-sm text-zinc-400">
          Displayed path and version metadata is the captured snapshot. Capture
          fresh path metadata above before further native action; a retained or
          uncertain cleanup item requires inspection.
        </p>
      )}
    </fieldset>
  );
}

function Rotations({
  snapshot,
  changed,
}: {
  snapshot: PathSnapshot;
  changed: Changed;
}) {
  const list = usePage<Rotation>(
      `/api/kv/rotations?pathId=${snapshot.path.id}`,
    ),
    task = useTask();
  const [field, setField] = useState(""),
    [kind, setKind] = useState("Deployment"),
    [consumer, setConsumer] = useState(""),
    [prepareConfirm, setPrepareConfirm] = useState(""),
    [row, setRow] = useState<Rotation | null>(null);
  const [confirm, setConfirm] = useState(""),
    [preview, setPreview] = useState<ConsumerPreview | null>(null),
    [consumerConfirm, setConsumerConfirm] = useState(""),
    [consumed, setConsumed] = useState(false),
    [finished, setFinished] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    if (task.error) {
      setFinished(true);
      setConfirm("");
      setPreview(null);
      setConsumerConfirm("");
      setConsumed(false);
    }
  }, [task.error]);
  const expected = row
    ? `${pathConfirmation(snapshot)} rotation=${row.id} revision=${row.revision} state=${row.state}`
    : "";
  const prepareExpected = `prepare ${snapshot.path.id} revision=${snapshot.path.revision} field=${field} consumer=${snapshot.path.namespace}/${kind}/${consumer}`;
  const clearAction = () => {
    setConfirm("");
    setPreview(null);
    setConsumerConfirm("");
    setConsumed(false);
  };
  const selected = (rotation: Rotation) => {
    setRow(rotation);
    clearAction();
  };
  const action = (
    name: "generate" | "cancel" | "resolve" | "acknowledge" | "reload",
  ) => {
    if (!row) return;
    void task.run(
      async (request) => {
        if (
          confirm !== expected ||
          !canAct(snapshot, "rotate", name !== "resolve" && name !== "cancel")
        )
          throw new AdminInputError(
            "Confirm the captured rotation and current permitted target.",
          );
        const base = {
          rotationId: row.id,
          revision: row.revision,
          confirmPath: snapshot.path.path,
        };
        const native = {
          resourceVersion: snapshot.status.resourceVersion,
          expectedHead: snapshot.status.head,
        };
        if (name === "reload") {
          if (
            !preview ||
            preview.rotationId !== row.id ||
            preview.revision !== row.revision ||
            consumerConfirm !==
              `${preview.consumer} uid=${preview.uid} rv=${preview.resourceVersion}`
          )
            throw new AdminInputError(
              "Capture and confirm the exact consumer UID/resourceVersion before requesting reload.",
            );
          return request<{ rotation: Rotation }>(
            `/api/kv/rotations/${row.id}/consumer`,
            "POST",
            {
              ...base,
              ...native,
              confirmConsumer: consumerTarget(row),
              consumerUid: preview.uid,
              consumerResourceVersion: preview.resourceVersion,
            },
          );
        }
        if (
          name === "acknowledge" &&
          (!consumed || consumerConfirm !== consumerTarget(row))
        )
          throw new AdminInputError(
            "Confirm the exact consumer and separately acknowledge consumption.",
          );
        return request<Rotation | { rotation: Rotation }>(
          "/api/kv/rotations",
          "PATCH",
          name === "resolve"
            ? { action: name, rotationId: row.id }
            : name === "cancel"
              ? { action: name, ...base }
              : {
                  action: name,
                  ...base,
                  ...native,
                  ...(name === "generate"
                    ? { pathRevision: snapshot.path.revision }
                    : {
                        confirmConsumer: consumerTarget(row),
                        confirmConsumption: true,
                      }),
                },
        );
      },
      (result) => {
        const updated = "rotation" in result ? result.rotation : result;
        setRow(updated);
        clearAction();
        if (name === "generate" || name === "reload" || name === "acknowledge")
          setFinished(true);
        setMessage(
          name === "reload"
            ? "Consumer template marker requested/verified. Pod readiness and consumption of the replacement remain unverified. Capture fresh metadata before acknowledgment."
            : name === "acknowledge"
              ? "Consumer consumption recorded as an explicit operator assertion; the application did not independently verify it."
              : name === "generate"
                ? "Static native replacement committed. No value was returned. Consumer reload and acknowledgment remain separate."
                : `Rotation ${name} metadata: ${updated.state}. No native retry or regeneration was sent.`,
        );
        list.refresh();
        changed("rotations");
      },
    );
  };
  return (
    <fieldset
      disabled={task.busy}
      aria-label="Rotations administration"
      className="space-y-4"
    >
      <p className="text-sm text-zinc-400">
        Static native replacement only: 32 random bytes encoded as base64url
        UTF-8. This does not rotate an external provider credential. Browsing
        this metadata never generates or reveals a replacement.
      </p>
      {list.controls}
      <TaskState task={list.task} />
      {list.page && (
        <Table
          headings={[
            "Rotation / state",
            "Field / declared consumer",
            "Inspect",
          ]}
        >
          {list.page.items.map((rotation) => (
            <tr key={rotation.id}>
              <td className="break-all">
                {rotation.id}
                <br />
                {rotation.state} · revision {rotation.revision}
                <br />
                <span className="text-xs text-zinc-400">
                  operation {rotation.operationId ?? "none"}
                </span>
              </td>
              <td className="break-all">
                {rotation.field}
                <br />
                {consumerTarget(rotation)}
              </td>
              <td>
                <Button disabled={task.busy} onClick={() => selected(rotation)}>
                  Select intent
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
      <div className={boxClass}>
        <h3 className="font-medium">Prepare explicit static rotation</h3>
        <Field label="Mapped field">
          <select
            className={inputClass}
            value={field}
            onChange={(event) => {
              setField(event.target.value);
              setPrepareConfirm("");
            }}
          >
            <option value="">Choose a mapped field</option>
            {snapshot.path.fields.map((mapping) => (
              <option key={mapping.field} value={mapping.field}>
                {mapping.field} → {mapping.key}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Same-namespace consumer kind">
          <select
            className={inputClass}
            value={kind}
            onChange={(event) => {
              setKind(event.target.value);
              setPrepareConfirm("");
            }}
          >
            {["Deployment", "StatefulSet", "DaemonSet"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </Field>
        <Field label={`Exact consumer name in ${snapshot.path.namespace}`}>
          <input
            className={inputClass}
            value={consumer}
            onChange={(event) => {
              setConsumer(event.target.value);
              setPrepareConfirm("");
            }}
          />
        </Field>
        <Exact
          expected={prepareExpected}
          value={prepareConfirm}
          onChange={setPrepareConfirm}
        />
        <Button
          disabled={
            task.busy ||
            finished ||
            !field ||
            !consumer ||
            !canAct(snapshot, "rotate") ||
            prepareConfirm !== prepareExpected
          }
          onClick={() => {
            void task.run(
              (request) =>
                request<Rotation>("/api/kv/rotations", "POST", {
                  pathId: snapshot.path.id,
                  pathRevision: snapshot.path.revision,
                  field,
                  consumer: {
                    kind,
                    namespace: snapshot.path.namespace,
                    name: consumer,
                  },
                }),
              (result) => {
                selected(result);
                setPrepareConfirm("");
                list.refresh();
                changed("rotations");
                setMessage(
                  "Rotation intent prepared; native values have not changed.",
                );
              },
            );
          }}
        >
          Prepare intent only
        </Button>
      </div>
      {row && (
        <div className={boxClass}>
          <h3 className="font-medium">Captured rotation workflow</h3>
          <p className="break-all text-sm">
            {row.id} · {row.state} · revision {row.revision}
            <br />
            field {row.field} · {consumerTarget(row)}
            <br />
            operation {row.operationId ?? "none"}
          </p>
          <Exact expected={expected} value={confirm} onChange={setConfirm} />
          <div className="flex flex-wrap gap-2">
            <Button
              danger
              disabled={
                task.busy ||
                finished ||
                confirm !== expected ||
                row.state !== "prepare" ||
                !!row.operationId ||
                !canAct(snapshot, "rotate")
              }
              onClick={() => action("generate")}
            >
              Generate static replacement once
            </Button>
            <Button
              disabled={
                task.busy ||
                confirm !== expected ||
                !canAct(snapshot, "rotate", false)
              }
              onClick={() => action("resolve")}
            >
              Inspect / resolve metadata outcome
            </Button>
            <Button
              danger
              disabled={
                task.busy ||
                confirm !== expected ||
                !["prepare", "conflict"].includes(row.state) ||
                !canAct(snapshot, "rotate", false)
              }
              onClick={() => action("cancel")}
            >
              Cancel eligible intent
            </Button>
          </div>
          <div className="space-y-3 border-t border-zinc-800 pt-3">
            <h4 className="text-sm font-medium">
              Explicit consumer reload / restart request
            </h4>
            <p className="text-xs text-zinc-400">
              Administrator plus rotate policy. This patches only the declared
              workload template marker with UID/RV tests. Flux may reconcile it
              back. A successful request does not prove rollout, readiness or
              consumption.
            </p>
            <Button
              disabled={
                task.busy ||
                finished ||
                row.state !== "awaiting-ack" ||
                !canAct(snapshot, "rotate", false)
              }
              onClick={() => {
                setPreview(null);
                setConsumerConfirm("");
                void task.run(
                  (request) =>
                    request<ConsumerPreview>(
                      `/api/kv/rotations/${row.id}/consumer`,
                    ),
                  (result) => {
                    if (
                      result.rotationId !== row.id ||
                      result.revision !== row.revision
                    )
                      throw new AdminInputError(
                        "Rotation changed during consumer preview. Capture fresh metadata.",
                      );
                    setPreview(result);
                  },
                );
              }}
            >
              Capture consumer UID / resourceVersion
            </Button>
            {preview && (
              <>
                <Exact
                  expected={`${preview.consumer} uid=${preview.uid} rv=${preview.resourceVersion}`}
                  value={consumerConfirm}
                  onChange={setConsumerConfirm}
                />
                <Button
                  danger
                  disabled={
                    task.busy ||
                    finished ||
                    confirm !== expected ||
                    !canAct(snapshot, "rotate") ||
                    consumerConfirm !==
                      `${preview.consumer} uid=${preview.uid} rv=${preview.resourceVersion}`
                  }
                  onClick={() => action("reload")}
                >
                  Request declared consumer restart once
                </Button>
              </>
            )}
          </div>
          <div className="space-y-3 border-t border-zinc-800 pt-3">
            <h4 className="text-sm font-medium">
              Separate consumer acknowledgment
            </h4>
            <p className="text-xs text-zinc-400">
              Use only after independently checking the consumer. The server
              requires this rotation to remain the current native head. The
              acknowledgment is your assertion, not an app observation.
            </p>
            <Field label="Type exact consumer target">
              <input
                className={inputClass}
                value={preview ? "" : consumerConfirm}
                onChange={(event) => {
                  setPreview(null);
                  setConsumerConfirm(event.target.value);
                }}
              />
            </Field>
            <Check
              label="I independently checked that this exact consumer received the replacement; record my consumption acknowledgment."
              checked={consumed}
              onChange={setConsumed}
            />
            <Button
              disabled={
                task.busy ||
                finished ||
                confirm !== expected ||
                !["awaiting-ack", "reload-requested"].includes(row.state) ||
                !consumed ||
                consumerConfirm !== consumerTarget(row) ||
                !canAct(snapshot, "rotate")
              }
              onClick={() => action("acknowledge")}
            >
              Record separate consumer acknowledgment
            </Button>
          </div>
        </div>
      )}
      <TaskState task={task} />
      {message && (
        <p role="status" className="text-sm text-amber-200">
          {message}
        </p>
      )}
      {finished && (
        <p className="text-sm text-zinc-400">
          Capture fresh path metadata above before any further native action.
        </p>
      )}
    </fieldset>
  );
}

const tabs = [
  "Policies",
  "Identities",
  "Audit",
  "Legacy lookup",
  "History & recovery",
  "Static rotation",
] as const;
type Tab = (typeof tabs)[number];
function Workspace({
  selectedPathId,
  changed,
  admin,
}: {
  selectedPathId: string | null;
  changed: Changed;
  admin: boolean;
}) {
  const [tab, setTab] = useState<Tab>(admin ? "Policies" : "Audit"),
    [pathId, setPathId] = useState(selectedPathId),
    [pathDraft, setPathDraft] = useState(selectedPathId ?? ""),
    [pathError, setPathError] = useState("");
  const pathTab = [
    "Legacy lookup",
    "History & recovery",
    "Static rotation",
  ].includes(tab);
  return (
    <div className="min-w-0 space-y-4">
      <nav
        aria-label="Engine administration views"
        className="flex flex-wrap gap-2"
      >
        {tabs
          .filter((value) => admin || value === "Audit")
          .map((value) => (
            <button
              type="button"
              key={value}
              aria-current={tab === value ? "page" : undefined}
              className={
                buttonClass +
                (tab === value
                  ? " border-indigo-500 bg-indigo-950 text-indigo-200"
                  : "")
              }
              onClick={() => setTab(value)}
            >
              {value}
            </button>
          ))}
      </nav>
      {!admin && (
        <p className="text-sm text-zinc-400">
          Fresh human engine administration is required for these management
          controls. Readonly and scoped writers retain their policy-filtered
          audit view; scoped KV and owner-token API permissions remain separate.
        </p>
      )}
      {pathTab && (
        <div className={boxClass}>
          <Field
            label="Explicit registered path UUID"
            hint="Copy an exact registered ID from mount/path metadata; no aliases or native targets are inferred."
          >
            <input
              className={inputClass}
              value={pathDraft}
              onChange={(event) => setPathDraft(event.target.value)}
            />
          </Field>
          <Button
            onClick={() => {
              if (!isUuid(pathDraft)) {
                setPathError("Enter an exact registered path UUID.");
                return;
              }
              setPathError("");
              setPathId(pathDraft);
            }}
          >
            Select path metadata
          </Button>
          {pathError && (
            <p role="alert" className="text-sm text-rose-300">
              {pathError}
            </p>
          )}
        </div>
      )}
      <div key={`${tab}:${pathId ?? "none"}`}>
        {tab === "Policies" && admin && <Policies changed={changed} />}
        {tab === "Identities" && admin && <Identities changed={changed} />}
        {tab === "Audit" && <AuditView pathId={pathId} />}
        {tab === "Legacy lookup" && admin && (
          <Legacy pathId={pathId} changed={changed} />
        )}
        {(tab === "History & recovery" || tab === "Static rotation") &&
          admin &&
          (pathId ? (
            <NativeAdministration
              pathId={pathId}
              rotation={tab === "Static rotation"}
              changed={changed}
            />
          ) : (
            <p className="text-sm text-zinc-400">
              Select an explicit registered path above.
            </p>
          ))}
      </div>
    </div>
  );
}

export function KvAdministration({
  selectedPathId = null,
  refreshKey = 0,
  active = true,
  initialOpen = false,
  onClose,
  onMetadataChange = noop,
}: KvAdministrationProps) {
  const session = useSession(),
    pathname = usePathname(),
    [open, setOpen] = useState(initialOpen),
    [epoch, setEpoch] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const clear = () => {
      setEpoch((value) => value + 1);
      setOpen(false);
      onClose?.();
    };
    const hidden = () => {
      if (document.visibilityState === "hidden") clear();
    };
    window.addEventListener("bortus-session-ended", clear);
    window.addEventListener("pagehide", clear);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      window.removeEventListener("bortus-session-ended", clear);
      window.removeEventListener("pagehide", clear);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [onClose]);
  const fresh =
    !!session.data?.authenticated &&
    !session.error &&
    Date.now() - session.updatedAt < 15000;
  useEffect(() => {
    if (open && active && fresh) heading.current?.focus();
  }, [open, active, fresh]);
  if (!active) return null;
  return (
    <section aria-label="BORTUS KV engine administration" className={boxClass}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-zinc-100">
            Engine administration
          </h2>
          <p className="text-sm text-zinc-400">
            Policies, scoped identities, audit, legacy access, history, recovery
            and static rotation.
          </p>
        </div>
        <Button
          disabled={!fresh}
          onClick={() => {
            setOpen(!open);
            setEpoch((value) => value + 1);
            if (open) onClose?.();
          }}
        >
          {open
            ? "Close administration and clear sensitive state"
            : "Open engine administration"}
        </Button>
      </div>
      {!fresh && (
        <p role="status" className="text-sm text-amber-200">
          Fresh authenticated session unavailable. Administration is closed
          until session metadata refreshes.
        </p>
      )}
      {open && fresh && (
        <Workspace
          key={`${pathname}:${refreshKey}:${epoch}:${selectedPathId ?? "none"}:${session.data?.username}:${session.canWrite}`}
          selectedPathId={selectedPathId}
          changed={onMetadataChange}
          admin={session.canWrite}
        />
      )}
    </section>
  );
}
export default KvAdministration;
