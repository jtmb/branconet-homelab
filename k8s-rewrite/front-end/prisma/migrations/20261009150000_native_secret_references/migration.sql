-- No secret values are imported, pushed, or deleted by this schema migration.
CREATE TABLE "secret_references" (
  "alias" TEXT NOT NULL PRIMARY KEY,
  "namespace" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "key" TEXT NOT NULL
);
