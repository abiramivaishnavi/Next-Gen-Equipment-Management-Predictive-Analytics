-- =====================================================================
-- EMS - Step B11 database changes.  Run ONCE in pgAdmin (Query Tool on ems_db).
-- Safe to run twice: every statement checks first.
--   1. EQUIPMENT.Capacity_Unit  (what the Capacity number is measured in)
--   2. Indexes for speed at scale (nothing changes in how the app behaves)
-- =====================================================================

-- 1) Capacity unit. Existing machines get 'tonnes' automatically (the default).
ALTER TABLE "EQUIPMENT" ADD COLUMN IF NOT EXISTS "Capacity_Unit" VARCHAR(20) NOT NULL DEFAULT 'tonnes';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'EQUIPMENT_Capacity_Unit_check') THEN
        ALTER TABLE "EQUIPMENT"
            ADD CONSTRAINT "EQUIPMENT_Capacity_Unit_check" CHECK ("Capacity_Unit" IN ('tonnes', 'm3', 'kW', 'litres'));
    END IF;
END $$;

-- 2) Indexes. PostgreSQL does not index foreign keys by itself; these make "history of one machine /
--    one project" lookups fast when the log tables grow into the hundreds of thousands of rows.
CREATE INDEX IF NOT EXISTS idx_fuel_log_equipment_date  ON "FUEL_LOG"("Equipment_ID", "Fuel_Date");
CREATE INDEX IF NOT EXISTS idx_fuel_log_project_date    ON "FUEL_LOG"("Project_ID", "Fuel_Date");
CREATE INDEX IF NOT EXISTS idx_util_equipment_date      ON "UTILIZATION_LOG"("Equipment_ID", "Log_Date");
CREATE INDEX IF NOT EXISTS idx_util_project_date        ON "UTILIZATION_LOG"("Project_ID", "Log_Date");
CREATE INDEX IF NOT EXISTS idx_breakdown_equipment_date ON "BREAKDOWN"("Equipment_ID", "Breakdown_Date");
CREATE INDEX IF NOT EXISTS idx_maintenance_equipment    ON "MAINTENANCE"("Equipment_ID", "Service_Date");
CREATE INDEX IF NOT EXISTS idx_repair_breakdown         ON "REPAIR"("Breakdown_ID");
CREATE INDEX IF NOT EXISTS idx_incident_equipment       ON "INCIDENT"("Equipment_ID", "Incident_Date");
CREATE INDEX IF NOT EXISTS idx_equipment_project        ON "EQUIPMENT"("Current_Project_ID");
CREATE INDEX IF NOT EXISTS idx_transfer_equipment       ON "TRANSFER"("Equipment_ID", "Transfer_Status");

-- Database-level backup for the application rule "only one Pending transfer per machine".
-- Created only if no machine currently has two Pending requests (otherwise it is skipped and you get a message).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM "TRANSFER" WHERE "Transfer_Status" = 'Pending'
               GROUP BY "Equipment_ID" HAVING count(*) > 1) THEN
        RAISE NOTICE 'SKIPPED uq_transfer_one_pending: some machine has 2 Pending transfers. Reject one, then run this script again.';
    ELSE
        CREATE UNIQUE INDEX IF NOT EXISTS uq_transfer_one_pending
            ON "TRANSFER"("Equipment_ID") WHERE "Transfer_Status" = 'Pending';
    END IF;
END $$;

-- One fuel price per fuel type per effective date (skipped with a message if duplicates exist).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM "FUEL_RATE" GROUP BY "Fuel_Type", "Effective_Date" HAVING count(*) > 1) THEN
        RAISE NOTICE 'SKIPPED uq_fuel_rate_type_date: the same fuel type has two prices for one date.';
    ELSE
        CREATE UNIQUE INDEX IF NOT EXISTS uq_fuel_rate_type_date ON "FUEL_RATE"("Fuel_Type", "Effective_Date");
    END IF;
END $$;

-- Check afterwards:
--   SELECT "Capacity_Unit", COUNT(*) FROM "EQUIPMENT" GROUP BY 1;          -- every machine: tonnes
--   SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY 1;  -- the idx_* names above
