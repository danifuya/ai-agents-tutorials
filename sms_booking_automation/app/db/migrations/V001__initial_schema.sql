-- V001: Initial database schema
-- Consolidated from init scripts: extensions, types, tables, functions, indexes, constraints, triggers

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Custom Types

CREATE TYPE public.event_type_enum AS ENUM (
    'wedding',
    'corporate',
    'birthday_party',
    'graduation',
    'anniversary',
    'family_reunion',
    'other'
);

CREATE TYPE public.job_status_enum AS ENUM (
    'pending_client_info',
    'ready_to_post',
    'applications_open'
);

-- Tables

CREATE TABLE public.clients (
    client_id bigint GENERATED ALWAYS AS IDENTITY,
    first_name text,
    last_name text,
    phone_number text,
    email_address text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE public.job_services (
    job_service_id bigint GENERATED ALWAYS AS IDENTITY,
    job_id bigint,
    service_id bigint,
    duration_hours numeric(4,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT job_services_duration_hours_check CHECK ((duration_hours > (0)::numeric))
);

CREATE TABLE public.jobs (
    job_id bigint GENERATED ALWAYS AS IDENTITY,
    client_id bigint NOT NULL,
    job_code text,
    event_date date,
    event_start_time time without time zone,
    event_address_street text,
    event_address_suburb text,
    event_address_state text,
    event_address_postcode character varying(20),
    guest_count integer,
    event_type public.event_type_enum,
    photographer_count integer,
    event_duration_hours numeric(4,2),
    job_status public.job_status_enum DEFAULT 'pending_client_info'::public.job_status_enum,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT jobs_photographer_count_check CHECK (photographer_count > 0)
);

CREATE TABLE public.services (
    service_id bigint GENERATED ALWAYS AS IDENTITY,
    name text NOT NULL,
    description text,
    base_price numeric(10,2),
    infographic_image_url text,
    code VARCHAR(50),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Functions
CREATE OR REPLACE FUNCTION update_updated_at_column() 
RETURNS TRIGGER 
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Indexes
CREATE INDEX idx_job_services_job_id ON public.job_services USING btree (job_id);
CREATE INDEX idx_job_services_service_id ON public.job_services USING btree (service_id);
CREATE UNIQUE INDEX services_code_unique ON services (code);
CREATE INDEX idx_services_code ON services (code);

-- Primary Keys and Constraints
ALTER TABLE ONLY public.clients ADD CONSTRAINT clients_pkey PRIMARY KEY (client_id);
ALTER TABLE ONLY public.job_services ADD CONSTRAINT job_services_job_id_service_id_key UNIQUE (job_id, service_id);
ALTER TABLE ONLY public.job_services ADD CONSTRAINT job_services_pkey PRIMARY KEY (job_service_id);
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_job_code_key UNIQUE (job_code);
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_pkey PRIMARY KEY (job_id);
ALTER TABLE ONLY public.services ADD CONSTRAINT services_pkey PRIMARY KEY (service_id);

-- Foreign Key Constraints
ALTER TABLE ONLY public.job_services ADD CONSTRAINT job_services_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(job_id) ON DELETE CASCADE;
ALTER TABLE ONLY public.job_services ADD CONSTRAINT job_services_service_id_fkey FOREIGN KEY (service_id) REFERENCES public.services(service_id) ON DELETE RESTRICT;
ALTER TABLE ONLY public.jobs ADD CONSTRAINT jobs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id) ON DELETE RESTRICT;

-- Triggers
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON public.clients FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_job_services_updated_at BEFORE UPDATE ON public.job_services FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_services_updated_at BEFORE UPDATE ON public.services FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Initial Data
-- Insert photography services
INSERT INTO services (code, name, base_price) VALUES
-- Wedding Photography Services
('wedding_ceremony', 'Wedding Ceremony Photography', 800.00),
('wedding_reception', 'Wedding Reception Photography', 600.00),
('wedding_full_day', 'Full Day Wedding Photography', 1200.00),

-- Portrait Photography Services
('portrait_individual', 'Individual Portrait Session', 250.00),
('portrait_family', 'Family Portrait Session', 350.00),
('portrait_corporate', 'Corporate Portrait Session', 400.00),

-- Event Photography Services
('event_corporate', 'Corporate Event Photography', 500.00),
('event_birthday', 'Birthday Party Photography', 300.00),
('event_graduation', 'Graduation Photography', 280.00),
('event_anniversary', 'Anniversary Photography', 320.00),

-- Photography Packages
('package_basic', 'Basic Photography Package', 450.00),
('package_standard', 'Standard Photography Package', 650.00),
('package_premium', 'Premium Photography Package', 950.00),
('package_deluxe', 'Deluxe Photography Package', 1400.00)

ON CONFLICT (code) DO NOTHING;
