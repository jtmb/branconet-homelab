import { QueryFailure } from "./query-store";

export type ConfigurationVariable = Record<string, unknown> & { id: string; key: string; value: string; category: string };
const invalid = () => new QueryFailure("Invalid configuration response. Refresh before trying again.", 502);
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
function variable(value: unknown): value is ConfigurationVariable {
  return record(value) && typeof value.id === "string" && value.id.length > 0
    && typeof value.key === "string" && typeof value.value === "string" && typeof value.category === "string";
}

export function configurationList(value: unknown): ConfigurationVariable[] {
  if (!Array.isArray(value) || !value.every(variable)) throw invalid();
  return value;
}

export function configurationSaved(value: unknown, expected: { id?: string; key: string; value: string; category: string }): void {
  const unverified = () => new QueryFailure("Configuration result could not be verified. The change may already have been saved. Refresh before trying again.", 502);
  if (!record(value) || value.success !== true || !variable(value.variable)) throw unverified();
  const saved = value.variable;
  if (saved.key !== expected.key || saved.value !== expected.value || saved.category !== expected.category
    || expected.id !== undefined && saved.id !== expected.id) throw unverified();
}

export function configurationRemoved(value: unknown): void {
  if (!record(value) || value.success !== true)
    throw new QueryFailure("Configuration removal could not be verified. The entry may already have been removed. Refresh before trying again.", 502);
}
