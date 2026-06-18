CREATE TABLE public.admin_users (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    restaurant_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(200) DEFAULT ''::character varying,
    role character varying(50) DEFAULT 'employee'::character varying,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.branches (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying(200) NOT NULL,
    address character varying(300) DEFAULT ''::character varying,
    city character varying(200) DEFAULT ''::character varying,
    phone character varying(50) DEFAULT ''::character varying,
    hours character varying(200) DEFAULT ''::character varying,
    maps_url text DEFAULT ''::text,
    is_open boolean DEFAULT true,
    is_default boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.branches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.contact_messages (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    name character varying(200) NOT NULL,
    email character varying(255) NOT NULL,
    phone character varying(50) DEFAULT ''::character varying,
    subject character varying(300) DEFAULT ''::character varying,
    message text NOT NULL,
    is_read boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.contact_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.content_pages (
    restaurant_id integer NOT NULL,
    slug character varying(100) NOT NULL,
    title character varying(200) DEFAULT ''::character varying,
    content text DEFAULT ''::text,
    updated_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.domains (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    domain character varying(255) NOT NULL,
    is_primary boolean DEFAULT false,
    verified boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.faqs (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    question text NOT NULL,
    answer text NOT NULL,
    category character varying(100) DEFAULT 'General'::character varying,
    order_index integer DEFAULT 0
);;

CREATE SEQUENCE public.faqs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.menu_items (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    category character varying(100) DEFAULT ''::character varying,
    name character varying(200) NOT NULL,
    description text DEFAULT ''::text,
    price numeric(10,2) NOT NULL,
    sale_price numeric(10,2),
    image text DEFAULT ''::text,
    rating numeric(3,1) DEFAULT 0,
    is_spicy boolean DEFAULT false,
    is_popular boolean DEFAULT false,
    is_featured boolean DEFAULT false,
    is_available boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.menu_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.order_claims (
    id integer NOT NULL,
    order_id character varying(20) NOT NULL,
    user_id text NOT NULL,
    receipt_number character varying(100) NOT NULL,
    status character varying(50) DEFAULT 'success'::character varying,
    failure_reason text DEFAULT ''::text,
    claimed_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.order_claims_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.orders (
    id character varying(20) NOT NULL,
    restaurant_id integer NOT NULL,
    user_id text,
    guest_name character varying(200) DEFAULT ''::character varying,
    guest_email character varying(255) DEFAULT ''::character varying,
    guest_phone character varying(50) DEFAULT ''::character varying,
    items jsonb DEFAULT '[]'::jsonb NOT NULL,
    subtotal numeric(10,2) DEFAULT 0,
    discount_amount numeric(10,2) DEFAULT 0,
    delivery_charge numeric(10,2) DEFAULT 0,
    total numeric(10,2) DEFAULT 0,
    status character varying(50) DEFAULT 'placed'::character varying,
    order_type character varying(50) DEFAULT 'delivery'::character varying,
    payment_method character varying(50) DEFAULT 'cash'::character varying,
    branch_id integer,
    address text DEFAULT ''::text,
    notes text DEFAULT ''::text,
    points_earned integer DEFAULT 0,
    points_redeemed integer DEFAULT 0,
    source character varying(50) DEFAULT 'online'::character varying,
    claim_code character varying(100),
    claimed_by_user_id text,
    claimed_at timestamp with time zone,
    claim_status character varying(50) DEFAULT 'unclaimed'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.platform_admins (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(200) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.points (
    user_id text NOT NULL,
    restaurant_id integer NOT NULL,
    points integer DEFAULT 0,
    updated_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.restaurants (
    id integer NOT NULL,
    name character varying(200) DEFAULT 'My Restaurant'::character varying NOT NULL,
    slug character varying(100) DEFAULT 'default'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.restaurants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.reward_settings (
    id integer NOT NULL,
    restaurant_id integer NOT NULL,
    mode character varying(50) DEFAULT 'points'::character varying,
    points_per_unit numeric(10,2) DEFAULT 1,
    unit_amount numeric(10,2) DEFAULT 100,
    min_redeem integer DEFAULT 100,
    max_discount numeric(10,2) DEFAULT 500,
    conversion_rate numeric(10,4) DEFAULT 1.0,
    eligible_category character varying(100) DEFAULT ''::character varying,
    eligible_item_id integer,
    required_count integer DEFAULT 10,
    free_item_id integer,
    auto_apply boolean DEFAULT false,
    claim_expiry_days integer DEFAULT 30,
    require_phone_match boolean DEFAULT false,
    updated_at timestamp with time zone DEFAULT now()
);;

CREATE SEQUENCE public.reward_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.settings (
    restaurant_id integer NOT NULL,
    key character varying(100) NOT NULL,
    value text DEFAULT ''::text,
    updated_at timestamp with time zone DEFAULT now()
);;

CREATE TABLE public.theme_settings (
    restaurant_id integer NOT NULL,
    primary_color character varying(20) DEFAULT '#e85d04'::character varying,
    secondary_color character varying(20) DEFAULT '#faa307'::character varying,
    accent_color character varying(20) DEFAULT '#f48c06'::character varying,
    logo_url text DEFAULT ''::text,
    favicon_url text DEFAULT ''::text,
    restaurant_name character varying(200) DEFAULT ''::character varying,
    hero_text character varying(300) DEFAULT ''::character varying,
    hero_subtext character varying(500) DEFAULT ''::character varying,
    font_family character varying(100) DEFAULT 'Inter'::character varying,
    updated_at timestamp with time zone DEFAULT now(),
    layout_style character varying(50) DEFAULT 'classic'::character varying,
    hero_image_url text DEFAULT ''::text,
    slogan character varying(80) DEFAULT ''::character varying
);;

CREATE TABLE public.users (
    id text DEFAULT (gen_random_uuid())::text NOT NULL,
    restaurant_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    first_name character varying(100) DEFAULT ''::character varying,
    last_name character varying(100) DEFAULT ''::character varying,
    phone character varying(50) DEFAULT ''::character varying,
    created_at timestamp with time zone DEFAULT now()
);;

ALTER TABLE ONLY public.branches ALTER COLUMN id SET DEFAULT nextval('public.branches_id_seq'::regclass);
ALTER TABLE ONLY public.contact_messages ALTER COLUMN id SET DEFAULT nextval('public.contact_messages_id_seq'::regclass);
ALTER TABLE ONLY public.domains ALTER COLUMN id SET DEFAULT nextval('public.domains_id_seq'::regclass);
ALTER TABLE ONLY public.faqs ALTER COLUMN id SET DEFAULT nextval('public.faqs_id_seq'::regclass);
ALTER TABLE ONLY public.menu_items ALTER COLUMN id SET DEFAULT nextval('public.menu_items_id_seq'::regclass);
ALTER TABLE ONLY public.order_claims ALTER COLUMN id SET DEFAULT nextval('public.order_claims_id_seq'::regclass);
ALTER TABLE ONLY public.restaurants ALTER COLUMN id SET DEFAULT nextval('public.restaurants_id_seq'::regclass);
ALTER TABLE ONLY public.reward_settings ALTER COLUMN id SET DEFAULT nextval('public.reward_settings_id_seq'::regclass);
SELECT pg_catalog.setval('public.branches_id_seq', 6, true);
SELECT pg_catalog.setval('public.contact_messages_id_seq', 1, false);
SELECT pg_catalog.setval('public.domains_id_seq', 2, true);
SELECT pg_catalog.setval('public.faqs_id_seq', 1, false);
SELECT pg_catalog.setval('public.menu_items_id_seq', 16, true);
SELECT pg_catalog.setval('public.order_claims_id_seq', 1, false);
SELECT pg_catalog.setval('public.restaurants_id_seq', 1, true);
SELECT pg_catalog.setval('public.reward_settings_id_seq', 1, true);
CREATE INDEX idx_branches_restaurant ON public.branches USING btree (restaurant_id);
CREATE INDEX idx_contact_messages_rest ON public.contact_messages USING btree (restaurant_id);
CREATE INDEX idx_faqs_restaurant ON public.faqs USING btree (restaurant_id);
CREATE INDEX idx_menu_items_rest_category ON public.menu_items USING btree (restaurant_id, category);
CREATE INDEX idx_menu_items_restaurant ON public.menu_items USING btree (restaurant_id);
CREATE INDEX idx_orders_claim_status ON public.orders USING btree (restaurant_id, claim_status);
CREATE INDEX idx_orders_restaurant_created ON public.orders USING btree (restaurant_id, created_at DESC);
CREATE INDEX idx_orders_restaurant_id ON public.orders USING btree (restaurant_id);
CREATE INDEX idx_orders_restaurant_status ON public.orders USING btree (restaurant_id, status);
CREATE INDEX idx_orders_user_id ON public.orders USING btree (user_id);