-- CreateTable
CREATE TABLE "variables" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "key" TEXT NOT NULL,
    "value" TEXT NOT NULL,
    "category" TEXT NOT NULL DEFAULT 'kubernetes',
    "encrypted" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "nodes" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "hostname" TEXT NOT NULL,
    "ipAddress" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'master',
    "status" TEXT NOT NULL DEFAULT 'pending',
    "cpu" INTEGER,
    "memory" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "jobs" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "playbook" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'running',
    "output" TEXT NOT NULL DEFAULT '',
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" DATETIME
);

-- CreateTable
CREATE TABLE "cluster_state" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "kubeconfig" TEXT NOT NULL DEFAULT '',
    "deployed" BOOLEAN NOT NULL DEFAULT false,
    "deployedAt" DATETIME,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "deployments" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespace" TEXT NOT NULL DEFAULT 'default',
    "replicas" INTEGER NOT NULL DEFAULT 1,
    "image" TEXT NOT NULL,
    "ports" JSONB,
    "env" JSONB,
    "volumes" JSONB,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "pods" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'Pending',
    "phase" TEXT,
    "reason" TEXT,
    "message" TEXT,
    "node" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "services" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "port" INTEGER NOT NULL,
    "targetPort" INTEGER,
    "protocol" TEXT NOT NULL DEFAULT 'TCP',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "pvc" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "capacity" TEXT,
    "accessModes" JSONB,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "longhorn_volumes" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "namespace" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "capacity" TEXT,
    "size" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "variables_key_key" ON "variables"("key");

-- CreateIndex
CREATE UNIQUE INDEX "nodes_hostname_key" ON "nodes"("hostname");

-- CreateIndex
CREATE UNIQUE INDEX "deployments_name_key" ON "deployments"("name");

-- CreateIndex
CREATE UNIQUE INDEX "pods_name_key" ON "pods"("name");

-- CreateIndex
CREATE UNIQUE INDEX "services_name_key" ON "services"("name");

-- CreateIndex
CREATE UNIQUE INDEX "pvc_name_key" ON "pvc"("name");

-- CreateIndex
CREATE UNIQUE INDEX "longhorn_volumes_name_key" ON "longhorn_volumes"("name");
