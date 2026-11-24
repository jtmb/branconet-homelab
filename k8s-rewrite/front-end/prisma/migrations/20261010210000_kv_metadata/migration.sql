-- CreateTable
CREATE TABLE "kv_mounts" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespaces" TEXT NOT NULL,
    "revision" INTEGER NOT NULL DEFAULT 1,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "kv_paths" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "mountId" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "retention" INTEGER NOT NULL DEFAULT 20,
    "revision" INTEGER NOT NULL DEFAULT 1,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "kv_paths_mountId_fkey" FOREIGN KEY ("mountId") REFERENCES "kv_mounts" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "kv_fields" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "pathId" TEXT NOT NULL,
    "field" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    CONSTRAINT "kv_fields_pathId_fkey" FOREIGN KEY ("pathId") REFERENCES "kv_paths" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "kv_policies" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "principal" TEXT NOT NULL,
    "mountId" TEXT,
    "prefix" TEXT NOT NULL DEFAULT '',
    "effect" TEXT NOT NULL,
    "actions" TEXT NOT NULL,
    "revision" INTEGER NOT NULL DEFAULT 1,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "kv_identities" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerId" TEXT NOT NULL,
    "ownerSessionVersion" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "credentialHash" TEXT NOT NULL,
    "expiresAt" DATETIME NOT NULL,
    "revokedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "kv_service_principals" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "revision" INTEGER NOT NULL DEFAULT 1
);

-- CreateTable
CREATE TABLE "kv_legacy_grants" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "pathId" TEXT NOT NULL,
    "alias" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "key" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "kv_operations" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "actorId" TEXT NOT NULL,
    "pathId" TEXT NOT NULL,
    "mountId" TEXT NOT NULL,
    "path" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "previousVersion" INTEGER,
    "newVersion" INTEGER,
    "outcome" TEXT NOT NULL DEFAULT 'pending',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "kv_audit" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "actorId" TEXT NOT NULL,
    "operationId" TEXT,
    "action" TEXT NOT NULL,
    "mountId" TEXT,
    "pathId" TEXT,
    "path" TEXT,
    "namespace" TEXT,
    "name" TEXT,
    "previousVersion" INTEGER,
    "newVersion" INTEGER,
    "outcome" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "kv_rotations" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "pathId" TEXT NOT NULL,
    "actorId" TEXT NOT NULL,
    "field" TEXT NOT NULL,
    "consumerKind" TEXT NOT NULL,
    "consumerNamespace" TEXT NOT NULL,
    "consumerName" TEXT NOT NULL,
    "state" TEXT NOT NULL DEFAULT 'prepare',
    "operationId" TEXT,
    "revision" INTEGER NOT NULL DEFAULT 1,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- Preserve the existing user table and all account data.
ALTER TABLE "users" ADD COLUMN "engineAdmin" BOOLEAN NOT NULL DEFAULT false;

-- CreateIndex
CREATE UNIQUE INDEX "kv_mounts_name_key" ON "kv_mounts"("name");

-- CreateIndex
CREATE INDEX "kv_paths_namespace_name_idx" ON "kv_paths"("namespace", "name");

-- CreateIndex
CREATE UNIQUE INDEX "kv_paths_mountId_path_key" ON "kv_paths"("mountId", "path");

-- CreateIndex
CREATE UNIQUE INDEX "kv_fields_pathId_field_key" ON "kv_fields"("pathId", "field");

-- CreateIndex
CREATE UNIQUE INDEX "kv_fields_namespace_name_key_key" ON "kv_fields"("namespace", "name", "key");

-- CreateIndex
CREATE INDEX "kv_policies_principal_idx" ON "kv_policies"("principal");

-- CreateIndex
CREATE UNIQUE INDEX "kv_identities_credentialHash_key" ON "kv_identities"("credentialHash");

-- CreateIndex
CREATE INDEX "kv_identities_ownerId_idx" ON "kv_identities"("ownerId");

-- CreateIndex
CREATE UNIQUE INDEX "kv_legacy_grants_pathId_alias_key" ON "kv_legacy_grants"("pathId", "alias");

-- CreateIndex
CREATE INDEX "kv_operations_pathId_createdAt_idx" ON "kv_operations"("pathId", "createdAt");

-- CreateIndex
CREATE INDEX "kv_audit_pathId_createdAt_idx" ON "kv_audit"("pathId", "createdAt");

-- CreateIndex
CREATE INDEX "kv_rotations_pathId_idx" ON "kv_rotations"("pathId");

-- Existing operators retain management and KV access; later accounts default
-- to metadata listing only. No credential values are read or migrated.
UPDATE "users" SET "engineAdmin" = true WHERE "role" = 'write';
INSERT INTO "kv_policies" ("id", "principal", "effect", "actions")
SELECT 'initial-' || "id", 'user:' || "id", 'allow',
  CASE WHEN "role" = 'write'
    THEN '["list","read","create","update","delete","rollback","reconcile","destroy","export","rotate"]'
    ELSE '["list"]' END
FROM "users";
INSERT INTO "kv_service_principals" ("id", "enabled") VALUES ('legacy-lookup', true);
