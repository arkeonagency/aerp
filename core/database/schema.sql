-- EUREKA MILESTONE 1: DATABASE SCHEMA

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- USER ROLES TYPE
CREATE TYPE user_role AS ENUM ('admin', 'staff', 'user');
CREATE TYPE payment_status AS ENUM ('unpaid', 'paid');
CREATE TYPE shipment_status AS ENUM ('quotation_created', 'rate_approved', 'payment_received', 'booked', 'uplifted', 'completed');

-- PROFILES TABLE
CREATE TABLE profiles (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    company_name TEXT,
    role user_role DEFAULT 'user',
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SHIPMENTS TABLE
CREATE TABLE shipments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_by BIGINT REFERENCES profiles(telegram_id),
    date DATE DEFAULT CURRENT_DATE,
    airline TEXT,
    awb_number TEXT,
    
    -- Cargo Physicals
    pieces INTEGER,
    gross_weight DECIMAL,
    length_cm DECIMAL,
    width_cm DECIMAL,
    height_cm DECIMAL,
    volumetric_weight DECIMAL,
    chargeable_weight DECIMAL,
    
    -- Financials
    approved_rate_usd DECIMAL,
    sale_rate_usd DECIMAL,
    exchange_rate_etb DECIMAL,
    
    -- Address Blocks
    shipper_info TEXT,
    consignee_info TEXT,
    notify_party TEXT,
    
    -- Status
    shipment_status shipment_status DEFAULT 'quotation_created',
    payment_status payment_status DEFAULT 'unpaid',
    
    -- Media Links
    files TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SETTINGS TABLE (For Global Variables)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value DECIMAL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial exchange rate
INSERT INTO settings (key, value) VALUES ('exchange_rate', 56.00);