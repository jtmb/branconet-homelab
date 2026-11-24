import prisma from "./db";
import { AliasCatalog, MAX_ALIASES, readAliasFile } from "./alias-catalog";
const scope = globalThis as typeof globalThis & { __bortusAliasCatalog?: AliasCatalog };
const catalog = scope.__bortusAliasCatalog ??= new AliasCatalog(async (path, signal) => Promise.all([
  readAliasFile(path, signal),
  prisma.secretReference.findMany({ take: MAX_ALIASES + 1, select: { alias: true, namespace: true, name: true, key: true } }),
]));
const file = () => process.env.BORTUS_SECRET_ALIASES_FILE || "";
export const listAliases = () => catalog.list(file());
export const pageAliases = (namespaces: ReadonlySet<string>, namespace: string | null, cursor: string | null) =>
  catalog.page(file(), namespaces, namespace, cursor);
export const resolveAlias = (alias: string) => catalog.resolve(file(), alias);
export const invalidateAliases = () => catalog.invalidate();
