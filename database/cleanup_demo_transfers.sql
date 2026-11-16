-- OPTIONAL one-time cleanup of the two demo transfers (#124 approved, #125 rejected).
-- Run in pgAdmin Query Tool on ems_db. It puts EQ-010 back on PRJ-008, where it was before demo #124.
-- Check the first SELECT before running the rest (both rows should be your demo rows).
SELECT "Transfer_ID", "Equipment_ID", "From_Project_ID", "To_Project_ID", "Transfer_Status", "Transfer_Notes"
FROM "TRANSFER" WHERE "Transfer_ID" IN (124, 125);

DELETE FROM "TRANSFER" WHERE "Transfer_ID" IN (124, 125);
UPDATE "EQUIPMENT" SET "Current_Project_ID" = 'PRJ-008' WHERE "Equipment_ID" = 'EQ-010';

-- Check: EQ-010 on PRJ-008, and no transfer #124/#125
SELECT "Equipment_ID", "Current_Project_ID" FROM "EQUIPMENT" WHERE "Equipment_ID" = 'EQ-010';
SELECT "Transfer_ID" FROM "TRANSFER" WHERE "Transfer_ID" IN (124, 125);
