-- =====================================================================
-- Next-Gen Equipment Management System (EMS) - database schema, version 4
-- Rebuilds an EMPTY ems_db from scratch. PostgreSQL 14+.
-- Generated from the live catalog export of 2026-10-31 (columns + constraints),
-- plus step B11 (2026-11-02): EQUIPMENT.Capacity_Unit. An EXISTING database gets the same change
-- from migrations_b11.sql (this file is for rebuilding an empty one).
-- Run with:  psql -U <user> -d ems_db -f migrations.sql
--
-- Contains: tables, keys, checks, reference rows (roles). No demo/sample data.
-- Section "RECOMMENDED INDEXES" at the bottom is NOT part of the verified export:
-- check what already exists first (see the query there).
-- Verified against the live database on 2026-10-31: NUMERIC precision/scale,
-- identity type (GENERATED ALWAYS on 9 tables; FUEL_RATE uses a sequence default)
-- and existing indexes (only the primary keys plus unique ROLE.Role_Name and EMPLOYEE.Email).
-- =====================================================================

CREATE TABLE "ROLE" (
    "Role_ID" SMALLINT GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Role_Name" VARCHAR(50) NOT NULL,
    "Role_Description" VARCHAR(255),
    CONSTRAINT "ROLE_pkey" PRIMARY KEY ("Role_ID"),
    CONSTRAINT "ROLE_Role_Name_key" UNIQUE ("Role_Name")
);

CREATE TABLE "EMPLOYEE" (
    "Employee_ID" VARCHAR(20) NOT NULL,
    "Employee_Name" VARCHAR(100) NOT NULL,
    "Email" VARCHAR(100) NOT NULL,
    "Phone" VARCHAR(20),
    "Role_ID" SMALLINT NOT NULL,
    "Employee_Status" VARCHAR(20) NOT NULL,
    "Password_Hash" VARCHAR(255),
    CONSTRAINT "EMPLOYEE_Role_ID_fkey" FOREIGN KEY ("Role_ID") REFERENCES "ROLE"("Role_ID"),
    CONSTRAINT "EMPLOYEE_pkey" PRIMARY KEY ("Employee_ID"),
    CONSTRAINT "EMPLOYEE_Email_key" UNIQUE ("Email")
);

CREATE TABLE "PROJECT" (
    "Project_ID" VARCHAR(20) NOT NULL,
    "Project_Name" VARCHAR(150) NOT NULL,
    "Location" VARCHAR(150),
    "Start_Date" DATE NOT NULL,
    "Expected_End_Date" DATE,
    "Project_Status" VARCHAR(20) NOT NULL,
    CONSTRAINT "PROJECT_check" CHECK (("Expected_End_Date" >= "Start_Date")),
    CONSTRAINT "PROJECT_pkey" PRIMARY KEY ("Project_ID")
);

CREATE TABLE "EQUIPMENT" (
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Equipment_Type" VARCHAR(50) NOT NULL,
    "Manufacturer" VARCHAR(100),
    "Model" VARCHAR(100),
    "Manufacturing_Year" SMALLINT NOT NULL,
    "Fuel_Type" VARCHAR(30) NOT NULL,
    "Capacity" NUMERIC(10,2),
    "Capacity_Unit" VARCHAR(20) NOT NULL DEFAULT 'tonnes',
    "Purchase_Date" DATE,
    "Current_Status" VARCHAR(30) NOT NULL,
    "Equipment_Name" VARCHAR(100) NOT NULL,
    "Current_Project_ID" VARCHAR(20),
    CONSTRAINT "EQUIPMENT_Capacity_check" CHECK (("Capacity" > (0)::numeric)),
    CONSTRAINT "EQUIPMENT_Capacity_Unit_check" CHECK ("Capacity_Unit" IN ('tonnes', 'm3', 'kW', 'litres')),
    CONSTRAINT "EQUIPMENT_Manufacturing_Year_check" CHECK (("Manufacturing_Year" >= 1900)),
    CONSTRAINT "EQUIPMENT_Current_Project_ID_fkey" FOREIGN KEY ("Current_Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "EQUIPMENT_pkey" PRIMARY KEY ("Equipment_ID")
);

CREATE TABLE "TRANSFER" (
    "Transfer_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "From_Project_ID" VARCHAR(20) NOT NULL,
    "To_Project_ID" VARCHAR(20) NOT NULL,
    "Requested_By" VARCHAR(20) NOT NULL,
    "Approved_By" VARCHAR(20),
    "Request_Date" DATE NOT NULL,
    "Effective_Transfer_Date" DATE,
    "Transfer_Status" VARCHAR(20) NOT NULL,
    "Rejection_Reason" VARCHAR(255),
    "Transfer_Notes" VARCHAR(255),
    CONSTRAINT "TRANSFER_check1" CHECK (("Effective_Transfer_Date" >= "Request_Date")),
    CONSTRAINT "TRANSFER_check" CHECK ((("To_Project_ID")::text <> ("From_Project_ID")::text)),
    CONSTRAINT "TRANSFER_Approved_By_fkey" FOREIGN KEY ("Approved_By") REFERENCES "EMPLOYEE"("Employee_ID"),
    CONSTRAINT "TRANSFER_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "TRANSFER_Requested_By_fkey" FOREIGN KEY ("Requested_By") REFERENCES "EMPLOYEE"("Employee_ID"),
    CONSTRAINT "TRANSFER_To_Project_ID_fkey" FOREIGN KEY ("To_Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "TRANSFER_From_Project_ID_fkey" FOREIGN KEY ("From_Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "TRANSFER_pkey" PRIMARY KEY ("Transfer_ID")
);

CREATE TABLE "PROJECT_ACTIVITY" (
    "Activity_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Project_ID" VARCHAR(20) NOT NULL,
    "Activity_Name" VARCHAR(150) NOT NULL,
    "Start_Date" DATE NOT NULL,
    "End_Date" DATE,
    "Expected_Intensity" VARCHAR(20),
    CONSTRAINT "PROJECT_ACTIVITY_check" CHECK (("End_Date" >= "Start_Date")),
    CONSTRAINT "PROJECT_ACTIVITY_Project_ID_fkey" FOREIGN KEY ("Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "PROJECT_ACTIVITY_pkey" PRIMARY KEY ("Activity_ID")
);

CREATE TABLE "UTILIZATION_LOG" (
    "Utilization_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Project_ID" VARCHAR(20) NOT NULL,
    "Log_Date" DATE NOT NULL,
    "Operating_Hours" NUMERIC(6,2) NOT NULL,
    CONSTRAINT "UTILIZATION_LOG_Operating_Hours_check" CHECK (("Operating_Hours" >= (0)::numeric)),
    CONSTRAINT "UTILIZATION_LOG_Project_ID_fkey" FOREIGN KEY ("Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "UTILIZATION_LOG_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "UTILIZATION_LOG_pkey" PRIMARY KEY ("Utilization_ID")
);

CREATE TABLE "FUEL_RATE" (
    "Fuel_Rate_ID" SERIAL,
    "Fuel_Type" VARCHAR(50) NOT NULL,
    "Rate_Per_Liter" NUMERIC(10,2) NOT NULL,
    "Effective_Date" DATE NOT NULL,
    CONSTRAINT "FUEL_RATE_Rate_Per_Liter_check" CHECK (("Rate_Per_Liter" > (0)::numeric)),
    CONSTRAINT "FUEL_RATE_pkey" PRIMARY KEY ("Fuel_Rate_ID")
);

CREATE TABLE "FUEL_LOG" (
    "Fuel_Log_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Project_ID" VARCHAR(20) NOT NULL,
    "Fuel_Date" DATE NOT NULL,
    "Fuel_Consumed" NUMERIC(10,2) NOT NULL,
    "Fuel_Cost" NUMERIC(12,2),
    CONSTRAINT "FUEL_LOG_Fuel_Cost_check" CHECK (("Fuel_Cost" >= (0)::numeric)),
    CONSTRAINT "FUEL_LOG_Fuel_Consumed_check" CHECK (("Fuel_Consumed" >= (0)::numeric)),
    CONSTRAINT "FUEL_LOG_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "FUEL_LOG_Project_ID_fkey" FOREIGN KEY ("Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "FUEL_LOG_pkey" PRIMARY KEY ("Fuel_Log_ID")
);

CREATE TABLE "INCIDENT" (
    "Incident_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Project_ID" VARCHAR(20) NOT NULL,
    "Incident_Date" DATE NOT NULL,
    "Incident_Type" VARCHAR(50) NOT NULL,
    "Severity" VARCHAR(20) NOT NULL,
    "Description" TEXT,
    "Incident_Time" TIME NOT NULL,
    "Incident_Type_Other" VARCHAR(150),
    CONSTRAINT "INCIDENT_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "INCIDENT_Project_ID_fkey" FOREIGN KEY ("Project_ID") REFERENCES "PROJECT"("Project_ID"),
    CONSTRAINT "INCIDENT_pkey" PRIMARY KEY ("Incident_ID")
);

CREATE TABLE "MAINTENANCE" (
    "Maintenance_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Service_Date" DATE NOT NULL,
    "Maintenance_Type" VARCHAR(50) NOT NULL,
    "Meter_Reading" NUMERIC(10,2),
    "Service_Details" TEXT,
    "Next_Service_Date" DATE,
    "Total_Cost" NUMERIC(12,2),
    CONSTRAINT "MAINTENANCE_Meter_Reading_check" CHECK (("Meter_Reading" >= (0)::numeric)),
    CONSTRAINT "MAINTENANCE_check" CHECK (("Next_Service_Date" >= "Service_Date")),
    CONSTRAINT "MAINTENANCE_Total_Cost_check" CHECK (("Total_Cost" >= (0)::numeric)),
    CONSTRAINT "MAINTENANCE_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "MAINTENANCE_pkey" PRIMARY KEY ("Maintenance_ID")
);

CREATE TABLE "BREAKDOWN" (
    "Breakdown_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Equipment_ID" VARCHAR(20) NOT NULL,
    "Breakdown_Date" DATE NOT NULL,
    "Description" TEXT,
    "Downtime_Hours" NUMERIC(8,2),
    "Breakdown_Status" VARCHAR(20) NOT NULL,
    CONSTRAINT "BREAKDOWN_Downtime_Hours_check" CHECK (("Downtime_Hours" >= (0)::numeric)),
    CONSTRAINT "BREAKDOWN_Equipment_ID_fkey" FOREIGN KEY ("Equipment_ID") REFERENCES "EQUIPMENT"("Equipment_ID"),
    CONSTRAINT "BREAKDOWN_pkey" PRIMARY KEY ("Breakdown_ID")
);

CREATE TABLE "REPAIR" (
    "Repair_ID" INTEGER GENERATED ALWAYS AS IDENTITY NOT NULL,
    "Breakdown_ID" INTEGER NOT NULL,
    "Repair_Date" DATE NOT NULL,
    "Parts_Replaced" TEXT,
    "Labor_Hours" NUMERIC(8,2),
    "Parts_Cost" NUMERIC(12,2),
    "Labor_Cost" NUMERIC(12,2),
    "Repair_Details" TEXT,
    CONSTRAINT "REPAIR_Labor_Hours_check" CHECK (("Labor_Hours" >= (0)::numeric)),
    CONSTRAINT "REPAIR_Labor_Cost_check" CHECK (("Labor_Cost" >= (0)::numeric)),
    CONSTRAINT "REPAIR_Parts_Cost_check" CHECK (("Parts_Cost" >= (0)::numeric)),
    CONSTRAINT "REPAIR_Breakdown_ID_fkey" FOREIGN KEY ("Breakdown_ID") REFERENCES "BREAKDOWN"("Breakdown_ID"),
    CONSTRAINT "REPAIR_pkey" PRIMARY KEY ("Repair_ID")
);

-- Reference data (not demo data): the three roles the application recognises.
INSERT INTO "ROLE" ("Role_Name", "Role_Description") VALUES
    ('Site Engineer',     'Data entry: equipment, fuel, utilization, incidents, transfer requests'),
    ('Workshop Mechanic', 'Service, breakdown and repair logs'),
    ('Fleet Manager',     'Approves transfers; oversight, reports, administration')
ON CONFLICT ("Role_Name") DO NOTHING;

-- =====================================================================
-- RECOMMENDED INDEXES (optional; migrations_b11.sql runs the same list on an existing database). PostgreSQL does not index foreign keys automatically.
-- First see what exists:   SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public';
-- =====================================================================
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
-- Database-level backup for the application rule "only one Pending request per equipment".
-- Run this only after:  SELECT "Equipment_ID" FROM "TRANSFER" WHERE "Transfer_Status"='Pending'
--                       GROUP BY 1 HAVING count(*) > 1;   returns no rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_transfer_one_pending ON "TRANSFER"("Equipment_ID") WHERE "Transfer_Status" = 'Pending';
-- One price per fuel type per effective date.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fuel_rate_type_date ON "FUEL_RATE"("Fuel_Type", "Effective_Date");
