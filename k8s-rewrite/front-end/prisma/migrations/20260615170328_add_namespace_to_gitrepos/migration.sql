-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_git_repos" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "branch" TEXT NOT NULL DEFAULT 'main',
    "path" TEXT NOT NULL DEFAULT './',
    "authMethod" TEXT NOT NULL DEFAULT 'none',
    "authData" TEXT NOT NULL DEFAULT '',
    "namespace" TEXT NOT NULL DEFAULT '',
    "syncInterval" TEXT NOT NULL DEFAULT '5m',
    "status" TEXT NOT NULL DEFAULT 'syncing',
    "lastSync" DATETIME,
    "lastError" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_git_repos" ("authData", "authMethod", "branch", "createdAt", "id", "lastError", "lastSync", "name", "path", "status", "syncInterval", "updatedAt", "url") SELECT "authData", "authMethod", "branch", "createdAt", "id", "lastError", "lastSync", "name", "path", "status", "syncInterval", "updatedAt", "url" FROM "git_repos";
DROP TABLE "git_repos";
ALTER TABLE "new_git_repos" RENAME TO "git_repos";
CREATE UNIQUE INDEX "git_repos_name_key" ON "git_repos"("name");
CREATE TABLE "new_nodes" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL DEFAULT '',
    "hostname" TEXT NOT NULL,
    "ipAddress" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'master',
    "status" TEXT NOT NULL DEFAULT 'pending',
    "cpu" INTEGER,
    "memory" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO "new_nodes" ("cpu", "createdAt", "hostname", "id", "ipAddress", "memory", "role", "status") SELECT "cpu", "createdAt", "hostname", "id", "ipAddress", "memory", "role", "status" FROM "nodes";
DROP TABLE "nodes";
ALTER TABLE "new_nodes" RENAME TO "nodes";
CREATE UNIQUE INDEX "nodes_hostname_key" ON "nodes"("hostname");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
