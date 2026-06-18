-- Baseline integrity fix: core tenant/catalog tables were created without
-- primary key constraints, which blocks foreign keys from Phase 0/1 tables
-- (customers, carts, order_line_items, analytics_events, etc.) referencing them.
-- Safe to apply: ids on these tables are already unique and non-null.
ALTER TABLE restaurants ADD CONSTRAINT restaurants_pkey PRIMARY KEY (id);
ALTER TABLE menu_items ADD CONSTRAINT menu_items_pkey PRIMARY KEY (id);
ALTER TABLE branches ADD CONSTRAINT branches_pkey PRIMARY KEY (id);
