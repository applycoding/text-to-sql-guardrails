-- SPDX-License-Identifier: Apache-2.0
DROP SCHEMA IF EXISTS shop CASCADE; CREATE SCHEMA shop;
CREATE TABLE shop.customers (id int PRIMARY KEY, name text NOT NULL, email text NOT NULL, city text NOT NULL, signup_date date NOT NULL);
CREATE TABLE shop.products (id int PRIMARY KEY, name text NOT NULL, category text NOT NULL, price_cents int NOT NULL);
CREATE TABLE shop.orders (id int PRIMARY KEY, customer_id int NOT NULL REFERENCES shop.customers, ordered_at date NOT NULL, status text NOT NULL);
CREATE TABLE shop.order_items (order_id int NOT NULL REFERENCES shop.orders, product_id int NOT NULL REFERENCES shop.products, quantity int NOT NULL, unit_price_cents int NOT NULL, PRIMARY KEY (order_id, product_id));
CREATE TABLE shop.staff_salaries (staff_id int PRIMARY KEY, name text, salary_cents int);
INSERT INTO shop.customers SELECT g, 'Customer ' || g, 'c' || g || '@example.test',
  (ARRAY['Denver','Boulder','Austin','Seattle','Portland','Chicago','Boston','Miami'])[1 + (g * 7) % 8],
  DATE '2024-01-01' + ((g * 37) % 730) FROM generate_series(1, 1000) g;
INSERT INTO shop.products SELECT g, 'Product ' || g, (ARRAY['books','games','garden','kitchen','music','sports'])[1 + (g * 5) % 6], 199 + (g * 113) % 9800 FROM generate_series(1, 120) g;
INSERT INTO shop.orders SELECT g, 1 + (g * 17) % 1000, DATE '2025-01-01' + ((g * 13) % 365), (ARRAY['placed','shipped','delivered','returned'])[1 + (g * 3) % 4] FROM generate_series(1, 8000) g;
INSERT INTO shop.order_items SELECT o, 1 + ((o * 11 + k * 29) % 120), 1 + (o + k) % 4, 0 FROM generate_series(1, 8000) o, generate_series(1, 3) k;
UPDATE shop.order_items oi SET unit_price_cents = p.price_cents FROM shop.products p WHERE p.id = oi.product_id;
INSERT INTO shop.staff_salaries SELECT g, 'Staff ' || g, 5000000 + g * 1000 FROM generate_series(1, 50) g;
ANALYZE;
