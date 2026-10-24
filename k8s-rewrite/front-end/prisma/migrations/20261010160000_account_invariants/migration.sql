ALTER TABLE "users" ADD COLUMN "sessionVersion" INTEGER NOT NULL DEFAULT 0;
CREATE TABLE "account_lock" (
  "id" INTEGER NOT NULL PRIMARY KEY,
  "locked" INTEGER NOT NULL DEFAULT 0
);
INSERT INTO "account_lock" ("id", "locked") VALUES (1, 0);
