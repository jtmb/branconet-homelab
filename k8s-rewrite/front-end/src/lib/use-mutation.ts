"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { MutationTask, MutationState } from "./mutation-task";
import { requestJson } from "./use-query";

export function useMutation(enabled = true) {
  const identity = useRef({ enabled });
  if (identity.current.enabled !== enabled) identity.current = { enabled };
  const owner = identity.current;
  const [state, setState] = useState<{ owner: typeof owner; value: MutationState }>({ owner, value: { busy: false, error: "" } });
  const task = useMemo(() => new MutationTask({ request: requestJson, changed: value => {
    if (identity.current === owner && owner.enabled) setState({ owner, value });
  } }), [owner]);
  useEffect(() => { if (owner.enabled) task.activate(); else task.dispose(); return () => task.dispose(); }, [task, owner]);
  return { ...(enabled && state.owner === owner ? state.value : { busy: false, error: "" }),
    mutate: <T>(url: string, init: RequestInit, success: (data: T) => void) => {
      if (identity.current !== owner || !owner.enabled) return;
      return task.run<T>(url, init, data => { if (identity.current === owner && owner.enabled) success(data); });
    }, clear: () => task.clear() };
}
