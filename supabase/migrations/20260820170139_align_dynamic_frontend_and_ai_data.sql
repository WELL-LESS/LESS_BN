-- Align persisted data with the latest dynamic Flutter screens and prepare
-- traceable inputs/outputs for the upcoming OpenAI Responses API integration.

create table public.skin_type_families (
  code text primary key,
  label text not null,
  title text not null,
  description text not null,
  display_order smallint not null,
  created_at timestamptz not null default now(),
  constraint skin_type_families_code_check check (code in ('O', 'D', 'C')),
  constraint skin_type_families_display_order_check check (display_order > 0)
);

insert into public.skin_type_families (code, label, title, description, display_order)
values
  ('O', '지성', '지성 피부', '피지 분비가 많고 모공이 넓은 유형', 10),
  ('D', '건성', '건성 피부', '수분과 유분이 부족해 건조함을 느끼는 유형', 20),
  ('C', '복합성', '복합성 피부', '부위에 따라 유분과 건조함이 함께 나타나는 유형', 30);

alter table public.skin_types
  add column family_code text;

update public.skin_types
set family_code = left(code, 1);

alter table public.skin_types
  alter column family_code set not null,
  add constraint skin_types_family_code_fkey
    foreign key (family_code) references public.skin_type_families(code) on delete restrict;

alter table public.skin_types
  drop constraint skin_types_oil_dry_axis_check,
  add constraint skin_types_oil_dry_axis_check check (oil_dry_axis in ('O', 'D', 'C'));

insert into public.skin_types (
  code,
  name,
  summary,
  oil_dry_axis,
  sensitive_resistant_axis,
  pigmented_nonpigmented_axis,
  family_code
)
values
  ('OSP', '지성·민감성·색소성', '피지 분비가 많고 외부 자극에 민감하며 색소 고민이 있는 피부', 'O', 'S', 'P', 'O'),
  ('OSN', '지성·민감성·비색소성', '피지 분비가 많고 외부 자극에 민감한 비색소성 피부', 'O', 'S', 'N', 'O'),
  ('ORP', '지성·저항성·색소성', '피지 분비가 많고 비교적 저항성이 있으며 색소 고민이 있는 피부', 'O', 'R', 'P', 'O'),
  ('ORN', '지성·저항성·비색소성', '피지 분비가 많고 비교적 저항성이 있는 비색소성 피부', 'O', 'R', 'N', 'O'),
  ('DSP', '건성·민감성·색소성', '건조함과 민감 반응, 색소 고민을 함께 관리해야 하는 피부', 'D', 'S', 'P', 'D'),
  ('DSN', '건성·민감성·비색소성', '건조하고 외부 자극에 민감한 비색소성 피부', 'D', 'S', 'N', 'D'),
  ('DRP', '건성·저항성·색소성', '건조하지만 비교적 저항성이 있으며 색소 고민이 있는 피부', 'D', 'R', 'P', 'D'),
  ('DRN', '건성·저항성·비색소성', '건조하지만 비교적 저항성이 있는 비색소성 피부', 'D', 'R', 'N', 'D'),
  ('CSP', '복합성·민감성·색소성', '부위별 유수분 차이와 민감 반응, 색소 고민이 함께 있는 피부', 'C', 'S', 'P', 'C'),
  ('CSN', '복합성·민감성·비색소성', '부위별 유수분 차이가 있고 외부 자극에 민감한 피부', 'C', 'S', 'N', 'C'),
  ('CRP', '복합성·저항성·색소성', '부위별 유수분 차이와 색소 고민이 있으며 비교적 저항성이 있는 피부', 'C', 'R', 'P', 'C'),
  ('CRN', '복합성·저항성·비색소성', '부위별 유수분 차이가 있고 비교적 저항성이 있는 피부', 'C', 'R', 'N', 'C')
on conflict (code) do update
set
  name = excluded.name,
  summary = excluded.summary,
  oil_dry_axis = excluded.oil_dry_axis,
  sensitive_resistant_axis = excluded.sensitive_resistant_axis,
  pigmented_nonpigmented_axis = excluded.pigmented_nonpigmented_axis,
  family_code = excluded.family_code;

create table public.diagnosis_images (
  id uuid primary key default gen_random_uuid(),
  diagnosis_id uuid not null references public.skin_diagnoses(id) on delete cascade,
  image_role text not null default 'FACE',
  bucket text not null default 'diagnosis-reports',
  object_path text not null,
  mime_type text not null,
  size_bytes bigint not null,
  width integer,
  height integer,
  display_order smallint not null default 1,
  created_at timestamptz not null default now(),
  constraint diagnosis_images_role_check check (image_role in ('FACE', 'REPORT', 'OTHER')),
  constraint diagnosis_images_mime_check check (mime_type in ('image/jpeg', 'image/png', 'image/webp')),
  constraint diagnosis_images_size_check check (size_bytes > 0 and size_bytes <= 10485760),
  constraint diagnosis_images_dimensions_check check (
    (width is null or width > 0) and (height is null or height > 0)
  ),
  constraint diagnosis_images_display_order_check check (display_order > 0),
  unique (diagnosis_id, image_role, display_order),
  unique (bucket, object_path)
);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'diagnosis-reports',
  'diagnosis-reports',
  false,
  10485760,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.products
  add column short_description text;

with demo_products (category_code, brand, name, short_description, is_aac, is_verified) as (
  values
    ('ESSENCE_SERUM_AMPOULE', 'MISSHA', '타임 레볼루션', '영양·재생 집중 케어', false, true),
    ('ESSENCE_SERUM_AMPOULE', 'Paula''s Choice', 'BHA 2%', '피지·각질 케어', false, true),
    ('ESSENCE_SERUM_AMPOULE', 'The Ordinary', '나이아신아마이드 10%', '모공·피지 개선', false, true),
    ('SKIN_TONER', 'COSRX', 'AHA/BHA 클라리파잉', '각질·피지 케어', false, true),
    ('SKIN_TONER', 'Klairs', '저자극 무향 토너', '수분 공급, pH 조절', false, true),
    ('CLEANSING_FOAM_GEL', 'COSRX', '오일-프리 클렌저', '약산성, 피지 조절', false, true),
    ('CREAM', 'Laneige', '워터뱅크 블루 HA', '보습 마무리', false, true),
    ('SUNSCREEN', 'Anessa', '퍼펙트 UV', '자외선 차단', false, true),
    ('ESSENCE_SERUM_AMPOULE', 'AAC', 'AAC 세이프 BHA 세럼', '민감 피부를 위한 저자극 BHA 케어', true, true)
)
insert into public.products (
  category_id,
  brand,
  name,
  short_description,
  source,
  is_aac,
  is_verified,
  price_amount,
  currency,
  image_bucket,
  image_path,
  metadata
)
select
  category.id,
  demo.brand,
  demo.name,
  demo.short_description,
  'OPERATOR',
  demo.is_aac,
  demo.is_verified,
  case when demo.is_aac then 48000 else null end,
  'KRW',
  case when demo.is_aac then 'product-catalog' else null end,
  case when demo.is_aac then 'aac/aac-safe-bha-serum.png' else null end,
  jsonb_build_object('demo_seed', true)
from demo_products as demo
join public.product_categories as category on category.code = demo.category_code
on conflict do nothing;

update public.products
set
  short_description = '민감 피부를 위한 저자극 BHA 케어',
  price_amount = 48000,
  image_bucket = 'product-catalog',
  image_path = 'aac/aac-safe-bha-serum.png',
  is_aac = true,
  is_verified = true
where lower(brand) = lower('AAC')
  and lower(name) = lower('AAC 세이프 BHA 세럼');

alter table public.routine_sessions
  add column analysis_summary text,
  add column score_breakdown jsonb not null default '{}'::jsonb;

alter table public.product_analyses
  add column score_breakdown jsonb not null default '{}'::jsonb,
  add column confidence numeric(4,3),
  add column prompt_version text,
  add constraint product_analyses_confidence_check check (
    confidence is null or confidence between 0 and 1
  );

alter table public.ai_analysis_runs
  add column provider_response_id text,
  add column response_schema_version text,
  add column request_fingerprint text,
  add column input_tokens integer,
  add column cached_input_tokens integer,
  add column output_tokens integer,
  add column reasoning_tokens integer,
  add column latency_ms integer,
  add column retry_count smallint not null default 0,
  add constraint ai_analysis_runs_input_tokens_check check (input_tokens is null or input_tokens >= 0),
  add constraint ai_analysis_runs_cached_tokens_check check (
    cached_input_tokens is null or cached_input_tokens >= 0
  ),
  add constraint ai_analysis_runs_output_tokens_check check (output_tokens is null or output_tokens >= 0),
  add constraint ai_analysis_runs_reasoning_tokens_check check (
    reasoning_tokens is null or reasoning_tokens >= 0
  ),
  add constraint ai_analysis_runs_latency_check check (latency_ms is null or latency_ms >= 0),
  add constraint ai_analysis_runs_retry_count_check check (retry_count between 0 and 10);

create unique index ai_analysis_runs_provider_response_id_uidx
  on public.ai_analysis_runs (provider_response_id)
  where provider_response_id is not null;

create index ai_analysis_runs_routine_status_idx
  on public.ai_analysis_runs (routine_id, status, queued_at desc);

create table public.ai_analysis_run_images (
  ai_analysis_run_id uuid not null references public.ai_analysis_runs(id) on delete cascade,
  product_scan_image_id uuid not null references public.product_scan_images(id) on delete cascade,
  image_variant text not null default 'ORIGINAL',
  input_detail text not null default 'AUTO',
  display_order smallint not null,
  created_at timestamptz not null default now(),
  primary key (ai_analysis_run_id, product_scan_image_id),
  constraint ai_analysis_run_images_variant_check check (image_variant in ('ORIGINAL', 'CUTOUT')),
  constraint ai_analysis_run_images_detail_check check (input_detail in ('LOW', 'HIGH', 'AUTO', 'ORIGINAL')),
  constraint ai_analysis_run_images_display_order_check check (display_order > 0)
);

create index diagnosis_images_diagnosis_id_idx
  on public.diagnosis_images (diagnosis_id, display_order);

create index skin_types_family_code_idx
  on public.skin_types (family_code, code);

alter table public.skin_type_families enable row level security;
alter table public.diagnosis_images enable row level security;
alter table public.ai_analysis_run_images enable row level security;

revoke all on public.skin_type_families from anon, authenticated;
revoke all on public.diagnosis_images from anon, authenticated;
revoke all on public.ai_analysis_run_images from anon, authenticated;

grant all privileges on public.skin_type_families to service_role;
grant all privileges on public.diagnosis_images to service_role;
grant all privileges on public.ai_analysis_run_images to service_role;

comment on table public.skin_type_families is 'O/D/C groups displayed by the dynamic diagnosis report screen.';
comment on table public.diagnosis_images is 'Private WHS diagnosis images; backend returns short-lived signed URLs only.';
comment on table public.ai_analysis_run_images is 'Exact original or cutout scan images supplied to each OpenAI run.';
comment on column public.ai_analysis_runs.input_payload is 'Normalized non-secret request snapshot; never store API keys or raw authorization headers.';
comment on column public.ai_analysis_runs.output_payload is 'Validated structured model output before normalization into product/routine analysis tables.';
