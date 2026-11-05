export const ANSIBLE_ROLES = ["bootstrap", "kubernetes", "network", "dns", "storage", "longhorn", "nfs", "samba", "ingress", "gitops", "secrets"] as const;
export type AnsibleRole = typeof ANSIBLE_ROLES[number];

export class AnsibleSelectionError extends Error {
  constructor() { super("Use site.yml and the supported provisioning roles"); }
}
export function ansibleSelection(playbook: unknown = "site.yml", roles: unknown = []) {
  if (playbook !== "site.yml" || !Array.isArray(roles) || roles.length > ANSIBLE_ROLES.length
      || roles.some(role => typeof role !== "string" || !(ANSIBLE_ROLES as readonly string[]).includes(role))
      || new Set(roles).size !== roles.length) throw new AnsibleSelectionError();
  return { playbook: "site.yml", roles: roles as AnsibleRole[] };
}
