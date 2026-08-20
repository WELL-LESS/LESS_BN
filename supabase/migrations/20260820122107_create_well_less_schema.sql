create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

revoke execute on function private.set_updated_at() from public, anon, authenticated;

create table public.skin_types (
  code text primary key,
  name text not null,
  summary text not null,
  oil_dry_axis text not null,
  sensitive_resistant_axis text not null,
  pigmented_nonpigmented_axis text not null,
  created_at timestamptz not null default now(),
  constraint skin_types_code_format check (code ~ '^[A-Z]{3,8}$'),
  constraint skin_types_oil_dry_axis_check check (oil_dry_axis in ('O', 'D')),
  constraint skin_types_sensitive_resistant_axis_check check (sensitive_resistant_axis in ('S', 'R')),
  constraint skin_types_pigmented_axis_check check (pigmented_nonpigmented_axis in ('P', 'N'))
);

create table public.diagnosis_codes (
  id uuid primary key default gen_random_uuid(),
  code_hash text not null unique,
  code_hint text,
  is_active boolean not null default true,
  expires_at timestamptz,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint diagnosis_codes_hash_format check (code_hash ~ '^[0-9a-f]{64}$')
);

create table public.access_sessions (
  id uuid primary key default gen_random_uuid(),
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete cascade,
  access_token_hash text not null unique,
  refresh_token_hash text unique,
  device_id_hash text,
  expires_at timestamptz not null,
  refresh_expires_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  constraint access_sessions_access_hash_format check (access_token_hash ~ '^[0-9a-f]{64}$'),
  constraint access_sessions_refresh_hash_format check (
    refresh_token_hash is null or refresh_token_hash ~ '^[0-9a-f]{64}$'
  ),
  constraint access_sessions_expiry_order check (
    refresh_expires_at is null or refresh_expires_at >= expires_at
  )
);

create table public.skin_diagnoses (
  id uuid primary key default gen_random_uuid(),
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete cascade,
  skin_type_code text not null references public.skin_types(code),
  diagnosed_at timestamptz not null,
  overall_summary text,
  disclaimer text not null default '본 결과는 의료적 진단이 아닙니다.',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (diagnosis_code_id, diagnosed_at)
);

create table public.diagnosis_axes (
  id bigint generated always as identity primary key,
  diagnosis_id uuid not null references public.skin_diagnoses(id) on delete cascade,
  axis_code text not null,
  selected_value text not null,
  score numeric(5,2) not null,
  created_at timestamptz not null default now(),
  constraint diagnosis_axes_code_check check (axis_code in ('O_D', 'S_R', 'P_N')),
  constraint diagnosis_axes_selected_check check (selected_value in ('O', 'D', 'S', 'R', 'P', 'N')),
  constraint diagnosis_axes_score_check check (score between 0 and 100),
  unique (diagnosis_id, axis_code)
);

create table public.diagnosis_metrics (
  id bigint generated always as identity primary key,
  diagnosis_id uuid not null references public.skin_diagnoses(id) on delete cascade,
  metric_code text not null,
  metric_name text not null,
  score numeric(5,2) not null,
  reference_score numeric(5,2),
  level text not null,
  display_order integer not null default 0,
  created_at timestamptz not null default now(),
  constraint diagnosis_metrics_code_format check (metric_code ~ '^[A-Z][A-Z0-9_]*$'),
  constraint diagnosis_metrics_score_check check (score between 0 and 100),
  constraint diagnosis_metrics_reference_score_check check (
    reference_score is null or reference_score between 0 and 100
  ),
  constraint diagnosis_metrics_level_check check (level in ('GOOD', 'NORMAL', 'CAUTION', 'HIGH')),
  constraint diagnosis_metrics_display_order_check check (display_order >= 0),
  unique (diagnosis_id, metric_code)
);

create table public.product_categories (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  icon_key text,
  default_order integer not null,
  is_required boolean not null default false,
  is_selectable boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint product_categories_code_format check (code ~ '^[A-Z][A-Z0-9_]*$'),
  constraint product_categories_order_check check (default_order > 0)
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  category_id uuid references public.product_categories(id) on delete set null,
  brand text not null,
  name text not null,
  source text not null default 'AI_DETECTED',
  is_aac boolean not null default false,
  is_verified boolean not null default false,
  price_amount bigint,
  currency text not null default 'KRW',
  image_bucket text,
  image_path text,
  purchase_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint products_source_check check (source in ('AAC_CATALOG', 'AI_DETECTED', 'OPERATOR')),
  constraint products_price_check check (price_amount is null or price_amount >= 0),
  constraint products_currency_check check (currency ~ '^[A-Z]{3}$')
);

create unique index products_normalized_name_uidx
  on public.products (lower(brand), lower(name));

create table public.ingredients (
  id uuid primary key default gen_random_uuid(),
  normalized_name text not null unique,
  display_name text not null,
  english_name text,
  aliases text[] not null default '{}',
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.product_ingredients (
  id bigint generated always as identity primary key,
  product_id uuid not null references public.products(id) on delete cascade,
  ingredient_id uuid not null references public.ingredients(id) on delete restrict,
  ingredient_order integer,
  raw_name text,
  source text not null default 'OPENAI',
  confidence numeric(4,3),
  created_at timestamptz not null default now(),
  constraint product_ingredients_order_check check (ingredient_order is null or ingredient_order > 0),
  constraint product_ingredients_source_check check (source in ('OPENAI', 'OPERATOR', 'MANUFACTURER')),
  constraint product_ingredients_confidence_check check (confidence is null or confidence between 0 and 1),
  unique (product_id, ingredient_id)
);

create table public.skin_ingredient_rules (
  id uuid primary key default gen_random_uuid(),
  skin_type_code text not null references public.skin_types(code) on delete cascade,
  ingredient_id uuid not null references public.ingredients(id) on delete cascade,
  effect text not null,
  score_delta numeric(5,2) not null default 0,
  severity text not null default 'MEDIUM',
  reason text not null,
  rule_version text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint skin_ingredient_rules_effect_check check (effect in ('BENEFICIAL', 'CAUTION', 'AVOID')),
  constraint skin_ingredient_rules_severity_check check (severity in ('LOW', 'MEDIUM', 'HIGH')),
  unique (skin_type_code, ingredient_id, rule_version)
);

create table public.routine_sessions (
  id uuid primary key default gen_random_uuid(),
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete cascade,
  diagnosis_id uuid not null references public.skin_diagnoses(id) on delete restrict,
  status text not null default 'DRAFT',
  overall_score numeric(5,2),
  started_at timestamptz not null default now(),
  confirmed_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint routine_sessions_status_check check (status in (
    'DRAFT', 'COMPOSING', 'COMPOSE_FAILED', 'REVIEW_REQUIRED', 'CONFIRMED',
    'ANALYZING', 'ANALYSIS_FAILED', 'DECISION_REQUIRED', 'COMPLETED'
  )),
  constraint routine_sessions_score_check check (overall_score is null or overall_score between 0 and 100)
);

create table public.routine_categories (
  routine_id uuid not null references public.routine_sessions(id) on delete cascade,
  category_id uuid not null references public.product_categories(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (routine_id, category_id)
);

create table public.product_scans (
  id uuid primary key default gen_random_uuid(),
  routine_id uuid not null references public.routine_sessions(id) on delete cascade,
  category_id uuid not null references public.product_categories(id) on delete restrict,
  matched_product_id uuid references public.products(id) on delete set null,
  client_product_id uuid,
  status text not null default 'UPLOADED',
  detected_brand text,
  detected_name text,
  ocr_text text,
  identification_confidence numeric(4,3),
  ai_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint product_scans_status_check check (status in (
    'UPLOADED', 'IDENTIFYING', 'IDENTIFIED', 'NEEDS_REVIEW', 'FAILED'
  )),
  constraint product_scans_confidence_check check (
    identification_confidence is null or identification_confidence between 0 and 1
  ),
  unique (routine_id, client_product_id)
);

create table public.product_scan_images (
  id uuid primary key default gen_random_uuid(),
  product_scan_id uuid not null references public.product_scans(id) on delete cascade,
  position smallint not null,
  image_role text not null default 'FRONT',
  original_bucket text not null default 'product-scans-original',
  original_path text not null,
  cutout_bucket text,
  cutout_path text,
  mime_type text not null,
  size_bytes bigint not null,
  width integer,
  height integer,
  exif_removed boolean not null default false,
  background_removed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint product_scan_images_position_check check (position between 1 and 3),
  constraint product_scan_images_role_check check (image_role in ('FRONT', 'INGREDIENTS', 'OTHER')),
  constraint product_scan_images_mime_check check (
    mime_type in ('image/jpeg', 'image/png', 'image/heic', 'image/heif', 'image/webp')
  ),
  constraint product_scan_images_size_check check (size_bytes > 0 and size_bytes <= 10485760),
  constraint product_scan_images_dimensions_check check (
    (width is null or width > 0) and (height is null or height > 0)
  ),
  unique (product_scan_id, position),
  unique (original_bucket, original_path)
);

create unique index product_scan_images_cutout_path_uidx
  on public.product_scan_images (cutout_bucket, cutout_path)
  where cutout_path is not null;

create table public.ai_analysis_runs (
  id uuid primary key default gen_random_uuid(),
  routine_id uuid references public.routine_sessions(id) on delete cascade,
  product_scan_id uuid references public.product_scans(id) on delete cascade,
  job_type text not null,
  status text not null default 'QUEUED',
  progress smallint not null default 0,
  provider text not null default 'OPENAI',
  model_name text,
  prompt_version text,
  analysis_version text,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb,
  error_code text,
  error_message text,
  queued_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint ai_analysis_runs_owner_check check (routine_id is not null or product_scan_id is not null),
  constraint ai_analysis_runs_job_type_check check (job_type in (
    'PRODUCT_IDENTIFICATION', 'INGREDIENT_EXTRACTION', 'ROUTINE_COMPOSITION', 'SUITABILITY_ANALYSIS'
  )),
  constraint ai_analysis_runs_status_check check (status in ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')),
  constraint ai_analysis_runs_progress_check check (progress between 0 and 100),
  constraint ai_analysis_runs_provider_check check (provider = 'OPENAI')
);

create table public.routine_items (
  id uuid primary key default gen_random_uuid(),
  routine_id uuid not null references public.routine_sessions(id) on delete cascade,
  product_scan_id uuid references public.product_scans(id) on delete set null,
  product_id uuid not null references public.products(id) on delete restrict,
  category_id uuid not null references public.product_categories(id) on delete restrict,
  position integer not null,
  source text not null default 'USER_PRODUCT',
  item_status text not null default 'ACTIVE',
  replaced_item_id uuid references public.routine_items(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint routine_items_position_check check (position > 0),
  constraint routine_items_source_check check (source in ('USER_PRODUCT', 'AAC_REPLACEMENT')),
  constraint routine_items_status_check check (item_status in ('ACTIVE', 'REMOVED', 'REPLACED')),
  constraint routine_items_position_unique unique (routine_id, position) deferrable initially deferred
);

create table public.product_analyses (
  id uuid primary key default gen_random_uuid(),
  routine_item_id uuid not null unique references public.routine_items(id) on delete cascade,
  score numeric(5,2) not null,
  verdict text not null,
  reasons text[] not null default '{}',
  flagged_ingredients jsonb not null default '[]'::jsonb,
  model_version text,
  analysis_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint product_analyses_score_check check (score between 0 and 100),
  constraint product_analyses_verdict_check check (verdict in ('KEEP', 'CHOICE', 'REMOVE'))
);

create table public.replacement_recommendations (
  id uuid primary key default gen_random_uuid(),
  product_analysis_id uuid not null references public.product_analyses(id) on delete cascade,
  replacement_product_id uuid not null references public.products(id) on delete restrict,
  replacement_score numeric(5,2),
  required_single_step boolean not null default false,
  reasons text[] not null default '{}',
  comparison jsonb not null default '{}'::jsonb,
  decision text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint replacement_recommendations_score_check check (
    replacement_score is null or replacement_score between 0 and 100
  ),
  constraint replacement_recommendations_decision_check check (
    decision is null or decision in ('REMOVE', 'REPLACE')
  ),
  unique (product_analysis_id, replacement_product_id)
);

create table public.carts (
  id uuid primary key default gen_random_uuid(),
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete cascade,
  routine_id uuid references public.routine_sessions(id) on delete set null,
  status text not null default 'ACTIVE',
  total_amount bigint not null default 0,
  currency text not null default 'KRW',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint carts_status_check check (status in ('ACTIVE', 'CONVERTED', 'ABANDONED')),
  constraint carts_total_check check (total_amount >= 0),
  constraint carts_currency_check check (currency ~ '^[A-Z]{3}$')
);

create unique index carts_one_active_per_code_uidx
  on public.carts (diagnosis_code_id)
  where status = 'ACTIVE';

create table public.cart_items (
  id uuid primary key default gen_random_uuid(),
  cart_id uuid not null references public.carts(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete restrict,
  recommendation_id uuid references public.replacement_recommendations(id) on delete set null,
  quantity integer not null default 1,
  unit_price bigint not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint cart_items_quantity_check check (quantity between 1 and 99),
  constraint cart_items_price_check check (unit_price >= 0),
  unique (cart_id, product_id)
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete restrict,
  routine_id uuid references public.routine_sessions(id) on delete set null,
  cart_id uuid references public.carts(id) on delete set null,
  order_number text not null unique,
  status text not null default 'PENDING_PAYMENT',
  payment_provider text not null default 'MOCK',
  payment_method text not null,
  subtotal_amount bigint not null,
  total_amount bigint not null,
  currency text not null default 'KRW',
  paid_at timestamptz,
  failed_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint orders_status_check check (status in ('PENDING_PAYMENT', 'PAID', 'PAYMENT_FAILED', 'CANCELLED')),
  constraint orders_provider_check check (payment_provider = 'MOCK'),
  constraint orders_method_check check (payment_method in ('KAKAO_PAY', 'NAVER_PAY', 'TOSS_PAY', 'CARD')),
  constraint orders_amount_check check (
    subtotal_amount >= 0 and total_amount >= 0 and total_amount <= subtotal_amount
  ),
  constraint orders_currency_check check (currency ~ '^[A-Z]{3}$')
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  product_id uuid references public.products(id) on delete set null,
  brand_snapshot text not null,
  name_snapshot text not null,
  unit_price bigint not null,
  quantity integer not null,
  line_total bigint generated always as (unit_price * quantity) stored,
  created_at timestamptz not null default now(),
  constraint order_items_price_check check (unit_price >= 0),
  constraint order_items_quantity_check check (quantity between 1 and 99)
);

create table public.analytics_events (
  id bigint generated always as identity primary key,
  diagnosis_code_id uuid references public.diagnosis_codes(id) on delete set null,
  access_session_id uuid references public.access_sessions(id) on delete set null,
  routine_id uuid references public.routine_sessions(id) on delete set null,
  event_name text not null,
  occurred_at timestamptz not null,
  properties jsonb not null default '{}'::jsonb,
  dedupe_key text unique,
  created_at timestamptz not null default now(),
  constraint analytics_events_name_check check (event_name in (
    'code_verified', 'inspection_started', 'routine_review_completed', 'analysis_viewed',
    'replacement_viewed', 'replacement_added', 'cart_viewed', 'checkout_started', 'payment_completed'
  ))
);

create table public.idempotency_records (
  id bigint generated always as identity primary key,
  diagnosis_code_id uuid not null references public.diagnosis_codes(id) on delete cascade,
  scope text not null,
  idempotency_key text not null,
  request_hash text not null,
  response_status integer,
  response_body jsonb,
  resource_id uuid,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  constraint idempotency_records_response_status_check check (
    response_status is null or response_status between 100 and 599
  ),
  unique (diagnosis_code_id, scope, idempotency_key)
);

create index access_sessions_diagnosis_code_id_idx on public.access_sessions (diagnosis_code_id);
create index access_sessions_active_idx on public.access_sessions (diagnosis_code_id, expires_at) where revoked_at is null;
create index skin_diagnoses_diagnosis_code_id_idx on public.skin_diagnoses (diagnosis_code_id);
create index skin_diagnoses_skin_type_code_idx on public.skin_diagnoses (skin_type_code);
create index diagnosis_axes_diagnosis_id_idx on public.diagnosis_axes (diagnosis_id);
create index diagnosis_metrics_diagnosis_id_idx on public.diagnosis_metrics (diagnosis_id);
create index products_category_id_idx on public.products (category_id);
create index product_ingredients_product_id_idx on public.product_ingredients (product_id);
create index product_ingredients_ingredient_id_idx on public.product_ingredients (ingredient_id);
create index skin_ingredient_rules_skin_type_code_idx on public.skin_ingredient_rules (skin_type_code);
create index skin_ingredient_rules_ingredient_id_idx on public.skin_ingredient_rules (ingredient_id);
create index routine_sessions_diagnosis_code_id_idx on public.routine_sessions (diagnosis_code_id);
create index routine_sessions_diagnosis_id_idx on public.routine_sessions (diagnosis_id);
create index routine_sessions_history_idx on public.routine_sessions (diagnosis_code_id, completed_at desc) where status = 'COMPLETED';
create index routine_categories_category_id_idx on public.routine_categories (category_id);
create index product_scans_routine_id_idx on public.product_scans (routine_id);
create index product_scans_category_id_idx on public.product_scans (category_id);
create index product_scans_matched_product_id_idx on public.product_scans (matched_product_id);
create index product_scan_images_product_scan_id_idx on public.product_scan_images (product_scan_id);
create index ai_analysis_runs_routine_id_idx on public.ai_analysis_runs (routine_id);
create index ai_analysis_runs_product_scan_id_idx on public.ai_analysis_runs (product_scan_id);
create index ai_analysis_runs_job_status_idx on public.ai_analysis_runs (status, queued_at);
create index routine_items_routine_id_idx on public.routine_items (routine_id);
create index routine_items_product_scan_id_idx on public.routine_items (product_scan_id);
create index routine_items_product_id_idx on public.routine_items (product_id);
create index routine_items_category_id_idx on public.routine_items (category_id);
create index routine_items_replaced_item_id_idx on public.routine_items (replaced_item_id);
create index replacement_recommendations_analysis_id_idx on public.replacement_recommendations (product_analysis_id);
create index replacement_recommendations_product_id_idx on public.replacement_recommendations (replacement_product_id);
create index carts_diagnosis_code_id_idx on public.carts (diagnosis_code_id);
create index carts_routine_id_idx on public.carts (routine_id);
create index cart_items_cart_id_idx on public.cart_items (cart_id);
create index cart_items_product_id_idx on public.cart_items (product_id);
create index cart_items_recommendation_id_idx on public.cart_items (recommendation_id);
create index orders_diagnosis_code_id_idx on public.orders (diagnosis_code_id);
create index orders_routine_id_idx on public.orders (routine_id);
create index orders_cart_id_idx on public.orders (cart_id);
create index order_items_order_id_idx on public.order_items (order_id);
create index order_items_product_id_idx on public.order_items (product_id);
create index analytics_events_diagnosis_code_id_idx on public.analytics_events (diagnosis_code_id);
create index analytics_events_access_session_id_idx on public.analytics_events (access_session_id);
create index analytics_events_routine_id_idx on public.analytics_events (routine_id);
create index analytics_events_name_time_idx on public.analytics_events (event_name, occurred_at desc);
create index idempotency_records_diagnosis_code_id_idx on public.idempotency_records (diagnosis_code_id);
create index idempotency_records_expiry_idx on public.idempotency_records (expires_at);

create trigger diagnosis_codes_set_updated_at
before update on public.diagnosis_codes
for each row execute function private.set_updated_at();
create trigger skin_diagnoses_set_updated_at
before update on public.skin_diagnoses
for each row execute function private.set_updated_at();
create trigger product_categories_set_updated_at
before update on public.product_categories
for each row execute function private.set_updated_at();
create trigger products_set_updated_at
before update on public.products
for each row execute function private.set_updated_at();
create trigger ingredients_set_updated_at
before update on public.ingredients
for each row execute function private.set_updated_at();
create trigger skin_ingredient_rules_set_updated_at
before update on public.skin_ingredient_rules
for each row execute function private.set_updated_at();
create trigger routine_sessions_set_updated_at
before update on public.routine_sessions
for each row execute function private.set_updated_at();
create trigger product_scans_set_updated_at
before update on public.product_scans
for each row execute function private.set_updated_at();
create trigger routine_items_set_updated_at
before update on public.routine_items
for each row execute function private.set_updated_at();
create trigger product_analyses_set_updated_at
before update on public.product_analyses
for each row execute function private.set_updated_at();
create trigger replacement_recommendations_set_updated_at
before update on public.replacement_recommendations
for each row execute function private.set_updated_at();
create trigger carts_set_updated_at
before update on public.carts
for each row execute function private.set_updated_at();
create trigger cart_items_set_updated_at
before update on public.cart_items
for each row execute function private.set_updated_at();
create trigger orders_set_updated_at
before update on public.orders
for each row execute function private.set_updated_at();

alter table public.skin_types enable row level security;
alter table public.diagnosis_codes enable row level security;
alter table public.access_sessions enable row level security;
alter table public.skin_diagnoses enable row level security;
alter table public.diagnosis_axes enable row level security;
alter table public.diagnosis_metrics enable row level security;
alter table public.product_categories enable row level security;
alter table public.products enable row level security;
alter table public.ingredients enable row level security;
alter table public.product_ingredients enable row level security;
alter table public.skin_ingredient_rules enable row level security;
alter table public.routine_sessions enable row level security;
alter table public.routine_categories enable row level security;
alter table public.product_scans enable row level security;
alter table public.product_scan_images enable row level security;
alter table public.ai_analysis_runs enable row level security;
alter table public.routine_items enable row level security;
alter table public.product_analyses enable row level security;
alter table public.replacement_recommendations enable row level security;
alter table public.carts enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.analytics_events enable row level security;
alter table public.idempotency_records enable row level security;

revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;

alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public grant all on tables to service_role;
alter default privileges for role postgres in schema public grant all on sequences to service_role;

comment on table public.diagnosis_codes is 'WHS personal code hashes; plaintext codes are never stored.';
comment on table public.access_sessions is 'Short-lived backend sessions issued after personal-code verification.';
comment on table public.product_scan_images is 'Original and background-removed image object paths for each product scan.';
comment on table public.ai_analysis_runs is 'Asynchronous OpenAI product, ingredient, routine, and suitability jobs.';
comment on table public.orders is 'Hackathon mock-payment order snapshots; no real PG payment data.';
