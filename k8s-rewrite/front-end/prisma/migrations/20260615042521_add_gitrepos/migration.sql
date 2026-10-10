-- CreateTable
CREATE TABLE "git_repos" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "branch" TEXT NOT NULL DEFAULT 'main',
    "path" TEXT NOT NULL DEFAULT './',
    "authMethod" TEXT NOT NULL DEFAULT 'none',
    "authData" TEXT NOT NULL DEFAULT '',
    "syncInterval" TEXT NOT NULL DEFAULT '5m',
    "status" TEXT NOT NULL DEFAULT 'syncing',
    "lastSync" DATETIME,
    "lastError" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "git_repos_name_key" ON "git_repos"("name");
