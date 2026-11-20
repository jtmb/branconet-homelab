-- Authorization metadata only. Preserve all existing rows and native values.
ALTER TABLE "kv_audit" ADD COLUMN "principal" TEXT;
ALTER TABLE "kv_audit" ADD COLUMN "alias" TEXT;
ALTER TABLE "kv_audit" ADD COLUMN "key" TEXT;
