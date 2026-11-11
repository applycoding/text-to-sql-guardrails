-- SPDX-License-Identifier: Apache-2.0
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 't2s_reader') THEN
  CREATE ROLE t2s_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT; END IF; END $$;
-- password set by seed.py from T2SQL_READER_PASSWORD (scram-sha-256 is the server default)
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE TEMP ON DATABASE <db> FROM PUBLIC;
GRANT USAGE ON SCHEMA shop TO t2s_reader;
GRANT SELECT ON shop.products, shop.orders, shop.order_items TO t2s_reader;
GRANT SELECT (id, name, city, signup_date) ON shop.customers TO t2s_reader;
ALTER ROLE t2s_reader SET default_transaction_read_only = on;
ALTER ROLE t2s_reader SET statement_timeout = '2s';
ALTER ROLE t2s_reader SET search_path = pg_catalog, shop, pg_temp;
