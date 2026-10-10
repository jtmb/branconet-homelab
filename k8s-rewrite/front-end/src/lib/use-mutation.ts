"use client";
import { useEffect, useMemo, useState } from "react";
import { MutationTask, MutationState } from "./mutation-task";
import { requestJson } from "./use-query";

export function useMutation() {
  const [state, setState] = useState<MutationState>({ busy: false, error: "" });
  const task = useMemo(() => new MutationTask({ request: requestJson, changed: setState }), []);
  useEffect(() => { task.activate(); return () => task.dispose(); }, [task]);
  return { ...state, mutate: task.run.bind(task), clear: () => task.clear() };
}
