-- Nonsecret UID/RV prerequisites for an explicitly requested consumer reload.
-- Existing rotation intent, operation and credential metadata remain unchanged.
ALTER TABLE "kv_rotations" ADD COLUMN "consumerUid" TEXT;
ALTER TABLE "kv_rotations" ADD COLUMN "consumerResourceVersion" TEXT;
