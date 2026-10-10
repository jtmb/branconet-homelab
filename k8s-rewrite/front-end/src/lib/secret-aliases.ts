import {
  SecretError,
  validateTarget,
  type SecretTarget,
} from "./cluster-secrets";
export type SecretAlias = SecretTarget & { alias: string };
export function validateAlias(ref: SecretAlias): SecretAlias {
  validateTarget(ref);
  if (
    typeof ref.alias !== "string" ||
    !/^[a-zA-Z0-9_.:/-]{1,253}$/.test(ref.alias)
  )
    throw new SecretError(400, "Invalid lookup alias");
  return {
    alias: ref.alias,
    namespace: ref.namespace,
    name: ref.name,
    key: ref.key,
  };
}
export function mergeAliases(groups: SecretAlias[][]): SecretAlias[] {
  const refs = new Map<string, SecretAlias>();
  for (const group of groups)
    for (const item of group) {
      const ref = validateAlias(item),
        existing = refs.get(ref.alias);
      if (
        existing &&
        (existing.namespace !== ref.namespace ||
          existing.name !== ref.name ||
          existing.key !== ref.key)
      )
        throw new SecretError(
          409,
          "Conflicting explicit lookup alias mappings",
        );
      refs.set(ref.alias, ref);
    }
  return [...refs.values()];
}
