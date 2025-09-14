-- V002: Remove event_address_suburb and event_address_state fields
-- These fields are being simplified to reduce data collection complexity

-- Remove the suburb and state columns from jobs table
ALTER TABLE public.jobs DROP COLUMN IF EXISTS event_address_suburb;
ALTER TABLE public.jobs DROP COLUMN IF EXISTS event_address_state;