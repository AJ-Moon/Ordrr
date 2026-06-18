# DO NOT run this on startup. If you need a new table, copy the relevant
# CREATE TABLE statement and run it manually in Supabase SQL Editor.

import os
import bcrypt
from db import get_db
from data.menu_data import menu_data
from data.branch_data import branch_data


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

DDL = """
-- Multi-tenant root table
CREATE TABLE IF NOT EXISTS restaurants (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL DEFAULT 'My Restaurant',
    slug         VARCHAR(100) UNIQUE NOT NULL DEFAULT 'default',
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name    VARCHAR(100) DEFAULT '',
    last_name     VARCHAR(100) DEFAULT '',
    phone         VARCHAR(50)  DEFAULT '',
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (restaurant_id, email)
);

CREATE TABLE IF NOT EXISTS admin_users (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(200) DEFAULT '',
    role          VARCHAR(50)  DEFAULT 'employee',
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (restaurant_id, email)
);

CREATE TABLE IF NOT EXISTS orders (
    id              VARCHAR(20) PRIMARY KEY,
    restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id),
    user_id         TEXT,
    guest_name      VARCHAR(200) DEFAULT '',
    guest_email     VARCHAR(255) DEFAULT '',
    guest_phone     VARCHAR(50)  DEFAULT '',
    items           JSONB        NOT NULL DEFAULT '[]',
    subtotal        DECIMAL(10,2) DEFAULT 0,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    delivery_charge DECIMAL(10,2) DEFAULT 0,
    total           DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(50)  DEFAULT 'placed',
    order_type      VARCHAR(50)  DEFAULT 'delivery',
    payment_method  VARCHAR(50)  DEFAULT 'cash',
    branch_id       INTEGER,
    address         TEXT         DEFAULT '',
    notes           TEXT         DEFAULT '',
    points_earned   INTEGER      DEFAULT 0,
    points_redeemed INTEGER      DEFAULT 0,
    source          VARCHAR(50)  DEFAULT 'online',
    claim_code      VARCHAR(100),
    claimed_by_user_id TEXT,
    claimed_at      TIMESTAMPTZ,
    claim_status    VARCHAR(50)  DEFAULT 'unclaimed',
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_claims (
    id             SERIAL PRIMARY KEY,
    order_id       VARCHAR(20)  NOT NULL REFERENCES orders(id),
    user_id        TEXT         NOT NULL,
    receipt_number VARCHAR(100) NOT NULL,
    status         VARCHAR(50)  DEFAULT 'success',
    failure_reason TEXT         DEFAULT '',
    claimed_at     TIMESTAMPTZ  DEFAULT NOW(),
    created_at     TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS points (
    user_id       TEXT NOT NULL,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    points        INTEGER DEFAULT 0,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    expires_at    TIMESTAMPTZ,
    PRIMARY KEY (user_id, restaurant_id)
);

CREATE TABLE IF NOT EXISTS points_transactions (
    id            SERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
    order_id      VARCHAR(20),
    type          VARCHAR(50) NOT NULL,
    points        INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_items (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    category      VARCHAR(100) DEFAULT '',
    name          VARCHAR(200) NOT NULL,
    description   TEXT         DEFAULT '',
    price         DECIMAL(10,2) NOT NULL,
    sale_price    DECIMAL(10,2),
    image         TEXT         DEFAULT '',
    rating        DECIMAL(3,1) DEFAULT 0,
    is_spicy      BOOLEAN      DEFAULT FALSE,
    is_popular    BOOLEAN      DEFAULT FALSE,
    is_featured   BOOLEAN      DEFAULT FALSE,
    is_available  BOOLEAN      DEFAULT TRUE,
    display_order INTEGER,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS branches (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    address       VARCHAR(300) DEFAULT '',
    city          VARCHAR(200) DEFAULT '',
    phone         VARCHAR(50)  DEFAULT '',
    hours         VARCHAR(200) DEFAULT '',
    maps_url      TEXT         DEFAULT '',
    is_open       BOOLEAN      DEFAULT TRUE,
    is_default    BOOLEAN      DEFAULT FALSE,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS faqs (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    category      VARCHAR(100) DEFAULT 'General',
    order_index   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS content_pages (
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    slug          VARCHAR(100) NOT NULL,
    title         VARCHAR(200) DEFAULT '',
    content       TEXT         DEFAULT '',
    updated_at    TIMESTAMPTZ  DEFAULT NOW(),
    PRIMARY KEY (restaurant_id, slug)
);

CREATE TABLE IF NOT EXISTS settings (
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    key           VARCHAR(100) NOT NULL,
    value         TEXT DEFAULT '',
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (restaurant_id, key)
);

CREATE TABLE IF NOT EXISTS contact_messages (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    phone         VARCHAR(50)  DEFAULT '',
    subject       VARCHAR(300) DEFAULT '',
    message       TEXT         NOT NULL,
    is_read       BOOLEAN      DEFAULT FALSE,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reward_settings (
    id              SERIAL PRIMARY KEY,
    restaurant_id   INTEGER UNIQUE NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    mode            VARCHAR(50)   DEFAULT 'points',
    points_per_unit DECIMAL(10,2) DEFAULT 1,
    unit_amount     DECIMAL(10,2) DEFAULT 100,
    min_redeem      INTEGER       DEFAULT 100,
    max_discount    DECIMAL(10,2) DEFAULT 500,
    conversion_rate DECIMAL(10,4) DEFAULT 1.0,
    eligible_category VARCHAR(100) DEFAULT '',
    eligible_item_id  INTEGER,
    required_count    INTEGER      DEFAULT 10,
    free_item_id      INTEGER,
    auto_apply        BOOLEAN      DEFAULT FALSE,
    claim_expiry_days INTEGER      DEFAULT 30,
    require_phone_match BOOLEAN    DEFAULT FALSE,
    updated_at        TIMESTAMPTZ  DEFAULT NOW()
);

-- Domain → restaurant mapping (multi-tenant hostname routing)
CREATE TABLE IF NOT EXISTS domains (
    id            SERIAL PRIMARY KEY,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    domain        VARCHAR(255) NOT NULL,
    is_primary    BOOLEAN     DEFAULT FALSE,
    verified      BOOLEAN     DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (domain)
);

-- Per-tenant visual theme
CREATE TABLE IF NOT EXISTS theme_settings (
    restaurant_id   INTEGER UNIQUE NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    primary_color   VARCHAR(20)  DEFAULT '#e85d04',
    secondary_color VARCHAR(20)  DEFAULT '#faa307',
    accent_color    VARCHAR(20)  DEFAULT '#f48c06',
    layout_style    VARCHAR(50)  DEFAULT 'classic',
    logo_url        TEXT         DEFAULT '',
    hero_image_url  TEXT         DEFAULT '',
    favicon_url     TEXT         DEFAULT '',
    restaurant_name VARCHAR(200) DEFAULT '',
    slogan          VARCHAR(80)  DEFAULT '',
    hero_text       VARCHAR(300) DEFAULT '',
    hero_subtext    VARCHAR(500) DEFAULT '',
    font_family     VARCHAR(100) DEFAULT 'Inter',
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- Platform-level super admins (manage all tenants; NOT restaurant admins)
CREATE TABLE IF NOT EXISTS platform_admins (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(200) DEFAULT '',
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- ── Performance indexes ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_orders_restaurant_id      ON orders(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_orders_restaurant_status  ON orders(restaurant_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_restaurant_created ON orders(restaurant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user_id            ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_claim_status       ON orders(restaurant_id, claim_status);
CREATE INDEX IF NOT EXISTS idx_menu_items_restaurant     ON menu_items(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_rest_category  ON menu_items(restaurant_id, category);
CREATE INDEX IF NOT EXISTS idx_menu_items_rest_display_order ON menu_items(restaurant_id, display_order);
CREATE INDEX IF NOT EXISTS idx_branches_restaurant       ON branches(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_faqs_restaurant           ON faqs(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_contact_messages_rest     ON contact_messages(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_points_transactions_user  ON points_transactions(user_id, restaurant_id);
CREATE INDEX IF NOT EXISTS idx_points_transactions_order ON points_transactions(order_id);
"""


def init_db() -> None:
    # Each phase uses its own short-lived connection so no single transaction is
    # held long enough for Supabase to kill it with an SSL EOF.

    # ── Phase 1: fast-path check ──────────────────────────────────────────────
    # Use pg_catalog (not information_schema) — fast on Supabase.
    # Sentinel: theme_settings.font_family is the most recently added column.
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = 'theme_settings'
                  AND a.attname = 'font_family'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                LIMIT 1
            """)
            _schema_current = cur.fetchone() is not None

    if not _schema_current:
        # ── Phase 2a: remove orphaned types ──────────────────────────────────
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DO $$
                        DECLARE r TEXT;
                        BEGIN
                            FOR r IN (
                                SELECT t.typname
                                FROM pg_type t
                                JOIN pg_namespace n ON n.oid = t.typnamespace
                                WHERE t.typtype = 'c'
                                  AND n.nspname = 'public'
                                  AND NOT EXISTS (
                                      SELECT 1 FROM pg_class c
                                      WHERE c.relname = t.typname
                                        AND c.relkind = 'r'
                                        AND c.relnamespace = n.oid
                                  )
                            ) LOOP
                                EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r) || ' CASCADE';
                            END LOOP;
                        END $$
                    """)
        except Exception:
            pass

        # ── Phase 2b: create tables ───────────────────────────────────────────
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(DDL)
        except Exception:
            pass

        # ── Phase 2c: add missing columns (migrations) ────────────────────────
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                DO $$
                DECLARE stmts TEXT[] := ARRAY[
                    'ALTER TABLE users ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50) DEFAULT ''''',
                    'ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS guest_name VARCHAR(200) DEFAULT ''''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS guest_email VARCHAR(255) DEFAULT ''''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(50) DEFAULT ''''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal DECIMAL(10,2) DEFAULT 0',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount DECIMAL(10,2) DEFAULT 0',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_charge DECIMAL(10,2) DEFAULT 0',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_type VARCHAR(50) DEFAULT ''delivery''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT ''cash''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS branch_id INTEGER',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS points_earned INTEGER DEFAULT 0',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS points_redeemed INTEGER DEFAULT 0',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT ''online''',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS claim_code VARCHAR(100)',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS claimed_by_user_id TEXT',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ',
                    'ALTER TABLE orders ADD COLUMN IF NOT EXISTS claim_status VARCHAR(50) DEFAULT ''unclaimed''',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS sale_price DECIMAL(10,2)',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_available BOOLEAN DEFAULT TRUE',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS display_order INTEGER',
                    'ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()',
                    'ALTER TABLE branches ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE branches ADD COLUMN IF NOT EXISTS maps_url TEXT DEFAULT ''''',
                    'ALTER TABLE branches ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE branches ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()',
                    'ALTER TABLE faqs ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE content_pages ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE content_pages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()',
                    'ALTER TABLE settings ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()',
                    'ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS phone VARCHAR(50) DEFAULT ''''',
                    'ALTER TABLE reward_settings ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE reward_settings ADD COLUMN IF NOT EXISTS claim_expiry_days INTEGER DEFAULT 30',
                    'ALTER TABLE reward_settings ADD COLUMN IF NOT EXISTS require_phone_match BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE points ADD COLUMN IF NOT EXISTS restaurant_id INTEGER',
                    'ALTER TABLE points ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ',
                    'ALTER TABLE domains ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT TRUE',
                    'ALTER TABLE domains ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT FALSE',
                    'ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS layout_style VARCHAR(50) DEFAULT ''classic''',
                    'ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS hero_image_url TEXT DEFAULT ''''',
                    'ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS slogan VARCHAR(80) DEFAULT ''''',
                    'ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS favicon_url TEXT DEFAULT ''''',
                    'ALTER TABLE theme_settings ADD COLUMN IF NOT EXISTS font_family VARCHAR(100) DEFAULT ''Inter'''
                ];
                s TEXT;
                BEGIN
                    FOREACH s IN ARRAY stmts LOOP
                        BEGIN
                            EXECUTE s;
                        EXCEPTION WHEN OTHERS THEN
                            NULL;
                        END;
                    END LOOP;
                END $$
                    """)
        except Exception:
            pass

    # ── Phase 3: ensure default restaurant ───────────────────────────────────
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM restaurants WHERE slug = 'default' LIMIT 1")
            row = cur.fetchone()
            if not row:
                restaurant_name = os.getenv("RESTAURANT_NAME", "Flavor Hub")
                cur.execute(
                    "INSERT INTO restaurants (name, slug) VALUES (%s, 'default') RETURNING id",
                    (restaurant_name,),
                )
                row = cur.fetchone()
            restaurant_id = row[0]

    if not _schema_current:
        # ── Phase 4: backfill restaurant_id on legacy rows ────────────────────
        _backfill_tables = [
            'users', 'admin_users', 'orders', 'menu_items',
            'branches', 'faqs', 'content_pages', 'settings',
            'contact_messages', 'reward_settings', 'points',
        ]
        for _tbl in _backfill_tables:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f'UPDATE {_tbl} SET restaurant_id = %s WHERE restaurant_id IS NULL',
                            (restaurant_id,),
                        )
            except Exception:
                pass

        # ── Phase 5: fix PKs / constraints ────────────────────────────────────
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint c
                                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                                WHERE c.conrelid = 'settings'::regclass
                                  AND c.contype = 'p'
                                  AND a.attname = 'restaurant_id'
                            ) THEN
                                ALTER TABLE settings DROP CONSTRAINT IF EXISTS settings_pkey;
                                ALTER TABLE settings ADD PRIMARY KEY (restaurant_id, key);
                            END IF;

                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint c
                                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                                WHERE c.conrelid = 'content_pages'::regclass
                                  AND c.contype = 'p'
                                  AND a.attname = 'restaurant_id'
                            ) THEN
                                ALTER TABLE content_pages DROP CONSTRAINT IF EXISTS content_pages_pkey;
                                ALTER TABLE content_pages ADD PRIMARY KEY (restaurant_id, slug);
                            END IF;

                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint c
                                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                                WHERE c.conrelid = 'domains'::regclass
                                  AND c.contype IN ('u', 'p')
                                  AND a.attname = 'domain'
                            ) THEN
                                ALTER TABLE domains ADD CONSTRAINT domains_domain_key UNIQUE (domain);
                            END IF;
                        END $$
                    """)
        except Exception:
            pass

    # ── Phase 6: seed data (all idempotent — skip if already present) ─────────
    with get_db() as conn:
        with conn.cursor() as cur:

            # Menu items
            cur.execute("SELECT COUNT(*) FROM menu_items WHERE restaurant_id = %s", (restaurant_id,))
            if cur.fetchone()[0] == 0:
                for item in menu_data:
                    cur.execute(
                        """INSERT INTO menu_items (restaurant_id, category, name, description, price, image, rating, is_spicy, is_popular)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (restaurant_id, item["category"], item["name"], item["description"],
                         item["price"], item["image"], item["rating"],
                         item["isSpicy"], item["isPopular"]),
                    )

            # Backfill missing display_order
            cur.execute("""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY restaurant_id, category
                               ORDER BY created_at, id
                           ) AS new_order
                    FROM menu_items
                    WHERE display_order IS NULL
                )
                UPDATE menu_items m
                SET display_order = ranked.new_order
                FROM ranked
                WHERE m.id = ranked.id
            """)

            # Branches
            cur.execute("SELECT COUNT(*) FROM branches WHERE restaurant_id = %s", (restaurant_id,))
            if cur.fetchone()[0] == 0:
                for b in branch_data:
                    cur.execute(
                        """INSERT INTO branches (restaurant_id, name, address, city, phone, hours, is_open)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (restaurant_id, b["name"], b["address"], b["city"], b["phone"], b["hours"], b["isOpen"]),
                    )

            # Content pages
            cur.execute("SELECT COUNT(*) FROM content_pages WHERE restaurant_id = %s", (restaurant_id,))
            if cur.fetchone()[0] == 0:
                for slug, title, content in [
                    ('privacy', 'Privacy Policy', 'Update your privacy policy here...'),
                    ('terms', 'Terms of Service', 'Update your terms of service here...'),
                    ('about', 'About Us', 'Tell your story here...'),
                    ('refund', 'Refund Policy', 'Update your refund policy here...'),
                ]:
                    cur.execute(
                        "INSERT INTO content_pages (restaurant_id, slug, title, content) VALUES (%s, %s, %s, %s)",
                        (restaurant_id, slug, title, content),
                    )

            # Default admin
            cur.execute("SELECT COUNT(*) FROM admin_users WHERE restaurant_id = %s", (restaurant_id,))
            if cur.fetchone()[0] == 0:
                email    = os.getenv("ADMIN_EMAIL",    "admin@flavorhub.com")
                password = os.getenv("ADMIN_PASSWORD", "Admin@FlavorHub123")
                cur.execute(
                    "INSERT INTO admin_users (restaurant_id, email, password_hash, name, role) VALUES (%s, %s, %s, 'Super Admin', 'admin')",
                    (restaurant_id, email, _hash_password(password)),
                )

            # Reward settings
            cur.execute("SELECT COUNT(*) FROM reward_settings WHERE restaurant_id = %s", (restaurant_id,))
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """INSERT INTO reward_settings (restaurant_id, mode, points_per_unit, unit_amount, min_redeem,
                       max_discount, conversion_rate, required_count, auto_apply, claim_expiry_days, require_phone_match)
                       VALUES (%s, 'points', 1, 100, 100, 500, 1.0, 10, false, 30, false)""",
                    (restaurant_id,),
                )

            # Default settings
            for k, v in {
                "delivery_charge": "0", "min_order_amount": "0",
                "points_on_guest": "false", "restaurant_open": "true",
                "points_per_dollar": "10", "min_redeem_points": "100",
                "points_value_cents": "1", "rewards_enabled": "true",
            }.items():
                cur.execute("SELECT 1 FROM settings WHERE restaurant_id = %s AND key = %s", (restaurant_id, k))
                if not cur.fetchone():
                    cur.execute("INSERT INTO settings (restaurant_id, key, value) VALUES (%s, %s, %s)", (restaurant_id, k, v))

            # Localhost domains (dev only)
            if restaurant_id == 1:
                for dev_domain in ["localhost", "127.0.0.1"]:
                    cur.execute("SELECT 1 FROM domains WHERE domain = %s", (dev_domain,))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO domains (restaurant_id, domain, is_primary, verified) VALUES (%s, %s, FALSE, TRUE)",
                            (restaurant_id, dev_domain),
                        )

            # Default theme
            cur.execute("SELECT name FROM restaurants WHERE id = %s", (restaurant_id,))
            restaurant_name = (cur.fetchone() or ("My Restaurant",))[0]
            cur.execute(
                """INSERT INTO theme_settings (restaurant_id, restaurant_name, hero_text, hero_subtext)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (restaurant_id) DO NOTHING""",
                (restaurant_id, restaurant_name,
                 f"Welcome to {restaurant_name}",
                 "Order fresh, delicious food delivered to your door."),
            )

            # Platform admin
            platform_email    = os.getenv("PLATFORM_ADMIN_EMAIL", "").strip()
            platform_password = os.getenv("PLATFORM_ADMIN_PASSWORD", "").strip()
            if platform_email and platform_password:
                cur.execute("SELECT COUNT(*) FROM platform_admins WHERE email = %s", (platform_email,))
                if cur.fetchone()[0] == 0:
                    cur.execute(
                        "INSERT INTO platform_admins (email, password_hash, name) VALUES (%s, %s, 'Platform Admin')",
                        (platform_email, _hash_password(platform_password)),
                    )

    print("✅ Database initialised successfully.")


if __name__ == "__main__":
    init_db()
