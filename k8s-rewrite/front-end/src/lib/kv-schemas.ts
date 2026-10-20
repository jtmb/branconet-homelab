import { z } from "zod";
import { KV_ACTIONS } from "./kv-contract";
export const revision = z.number().int().positive().optional();
export const mountCreate = z.object({ name: z.string(), namespaces: z.array(z.string()).min(1).max(128) }).strict();
export const mountUpdate = mountCreate.partial().extend({ revision }).strict().refine(v => v.name !== undefined || v.namespaces !== undefined);
export const removeMetadata = z.object({ revision }).strict();
export const pathCreate = z.object({ mountId: z.string().uuid(), path: z.string(), namespace: z.string(), name: z.string(), fields: z.array(z.object({ field: z.string(), key: z.string() }).strict()).min(1).max(64), retention: z.number().int().optional() }).strict();
export const pathUpdate = z.object({ revision, retention: z.number().int() }).strict();
export const policyFields = z.object({ principal: z.string().max(128), mountId: z.string().uuid().nullable(), prefix: z.string(), effect: z.enum(["allow", "deny"]), actions: z.array(z.enum(KV_ACTIONS)).min(1).max(10) }).strict();
export const legacyAcknowledgement = z.object({ fingerprint: z.string().regex(/^[a-f0-9]{64}$/), aliases: z.array(z.string().max(253)).max(10000), confirmLegacyImpact: z.literal(true), confirmConfigurationImpact: z.literal(true).optional() }).strict();
export const policyCreateRequest = policyFields.extend({ legacyImpact: legacyAcknowledgement.optional() }).strict();
export const policyUpdate = policyCreateRequest.extend({ revision }).strict();
export const policyRemove = removeMetadata.extend({ legacyImpact: legacyAcknowledgement.optional() }).strict();
const legacyCursor = z.string().regex(/^[a-zA-Z0-9_.:/-]{1,253}$/).optional();
export const policyPreview = z.discriminatedUnion("action", [policyFields.extend({ action: z.literal("create"), cursor: legacyCursor }).strict(),
  policyFields.extend({ action: z.literal("update"), id: z.string().uuid(), revision, cursor: legacyCursor }).strict(),
  z.object({ action: z.literal("delete"), id: z.string().uuid(), revision, cursor: legacyCursor }).strict()]);
export const legacyPrincipal = z.object({ enabled: z.boolean(), revision, legacyImpact: legacyAcknowledgement.optional() }).strict();
export const legacyGrant = z.object({ pathId: z.string().uuid(), pathRevision: revision, alias: z.string().max(253), revision, legacyImpact: legacyAcknowledgement.optional() }).strict();
export const legacyRevoke = z.object({ revision, legacyImpact: legacyAcknowledgement.optional() }).strict();
export const legacyPreview = z.discriminatedUnion("kind", [legacyPrincipal.omit({ legacyImpact: true }).extend({ kind: z.literal("principal"), cursor: legacyCursor }).strict(),
  legacyGrant.omit({ legacyImpact: true }).extend({ kind: z.literal("grant"), cursor: legacyCursor }).strict(),
  legacyRevoke.omit({ legacyImpact: true }).extend({ kind: z.literal("revoke"), grantId: z.string().uuid(), cursor: legacyCursor }).strict()]);
export const identityRevoke = z.object({ revision: z.string().regex(/^[a-f0-9]{64}$/).optional() }).strict();
export const identityCreate = z.object({ ownerId: z.string().max(128), name: z.string(), expiresAt: z.string().datetime(), scopes: z.array(z.object({ mountId: z.string().uuid(), prefix: z.string(), actions: z.array(z.enum(KV_ACTIONS)).min(1).max(10) }).strict()).min(1).max(32) }).strict();
export const nativePrerequisites = { resourceVersion: z.string().max(128).optional(), expectedHead: z.number().int().nonnegative().optional(), pathRevision: z.number().int().positive().safe().optional() };
export const encodedField = z.object({ field: z.string(), encoding: z.enum(["utf8", "base64"]), value: z.string() }).strict();
export const dataChange = z.object({ ...nativePrerequisites, fields: z.array(encodedField).max(64) }).strict();
export const nativeAdopt = z.object({ ...nativePrerequisites, legacyAliases: z.array(z.string().max(253)).max(10000) }).strict();
export const nativeReconcile = z.object(nativePrerequisites).strict();
export const nativeRollback = z.object({ ...nativePrerequisites, version: z.number().int().positive() }).strict();
export const nativeDelete = z.object({ ...nativePrerequisites, confirmPath: z.string() }).strict();
export const nativeDestroy = nativeDelete.extend({ versions: z.array(z.number().int().positive()).min(1).max(100),
  sourceUid: z.string().min(1).max(128).optional(),
  histories: z.array(z.object({ version: z.number().int().positive(), name: z.string().regex(/^kv-[0-9a-f]{32}-[0-9a-f]{24}$/), uid: z.string().min(1).max(128) }).strict()).min(1).max(100).optional() }).strict();
export const historyGcPreview = z.object({ pathId: z.string().uuid() }).strict();
export const historyGc = nativeDelete.extend({ pathId: z.string().uuid(), pathRevision: z.number().int().positive(),
  histories: z.array(z.object({ name: z.string().regex(/^kv-[0-9a-f]{32}-[0-9a-f]{24}$/), uid: z.string().min(1).max(128), resourceVersion: z.string().min(1).max(128) }).strict()).min(1).max(100) }).strict();
export const rotationPrepare = z.object({ pathId: z.string().uuid(), pathRevision: z.number().int().positive(), field: z.string().min(1).max(253),
  consumer: z.object({ kind: z.enum(["Deployment", "StatefulSet", "DaemonSet"]), namespace: z.string().min(1).max(63), name: z.string().min(1).max(253) }).strict() }).strict();
export const rotationTarget = { rotationId: z.string().uuid() };
export const rotationGenerate = z.object({ ...rotationTarget, ...nativePrerequisites, pathRevision: z.number().int().positive(), revision: z.number().int().positive(), confirmPath: z.string().max(512) }).strict();
export const rotationAcknowledge = rotationGenerate.omit({ pathRevision: true }).extend({ confirmConsumer: z.string().max(384), confirmConsumption: z.literal(true) }).strict();
export const rotationCancel = z.object({ ...rotationTarget, revision: z.number().int().positive(), confirmPath: z.string().max(512) }).strict();
export const rotationReload = rotationGenerate.omit({ pathRevision: true }).extend({ confirmConsumer: z.string().max(384), consumerUid: z.string().min(1).max(128), consumerResourceVersion: z.string().min(1).max(128) }).strict();
export const rotationAction = z.discriminatedUnion("action", [
  rotationGenerate.extend({ action: z.literal("generate") }).strict(),
  rotationAcknowledge.extend({ action: z.literal("acknowledge") }).strict(),
  rotationCancel.extend({ action: z.literal("cancel") }).strict(),
  z.object({ ...rotationTarget, action: z.literal("resolve") }).strict(),
]);
