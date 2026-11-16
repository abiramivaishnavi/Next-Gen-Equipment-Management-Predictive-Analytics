-- EMS step B7: optional reason/notes on a transfer request.
-- Safe to run more than once.
ALTER TABLE "TRANSFER" ADD COLUMN IF NOT EXISTS "Transfer_Notes" VARCHAR(255);
-- (already added earlier; included so a fresh database also gets it)
ALTER TABLE "TRANSFER" ADD COLUMN IF NOT EXISTS "Rejection_Reason" VARCHAR(255);
