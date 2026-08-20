insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  (
    'product-scans-original',
    'product-scans-original',
    false,
    10485760,
    array['image/jpeg', 'image/png', 'image/heic', 'image/heif']
  ),
  (
    'product-scans-cutout',
    'product-scans-cutout',
    false,
    10485760,
    array['image/png', 'image/webp']
  ),
  (
    'product-catalog',
    'product-catalog',
    true,
    5242880,
    array['image/jpeg', 'image/png', 'image/webp']
  )
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

insert into public.skin_types (
  code,
  name,
  summary,
  oil_dry_axis,
  sensitive_resistant_axis,
  pigmented_nonpigmented_axis
)
values
  ('OSP', '지성·민감성·색소성', '피지 분비가 많고 외부 자극에 민감하며 색소 고민이 있는 피부', 'O', 'S', 'P'),
  ('OSN', '지성·민감성·비색소성', '피지 분비가 많고 외부 자극에 민감한 비색소성 피부', 'O', 'S', 'N'),
  ('ORP', '지성·저항성·색소성', '피지 분비가 많고 비교적 저항성이 있으며 색소 고민이 있는 피부', 'O', 'R', 'P'),
  ('ORN', '지성·저항성·비색소성', '피지 분비가 많고 비교적 저항성이 있는 비색소성 피부', 'O', 'R', 'N')
on conflict (code) do update
set
  name = excluded.name,
  summary = excluded.summary,
  oil_dry_axis = excluded.oil_dry_axis,
  sensitive_resistant_axis = excluded.sensitive_resistant_axis,
  pigmented_nonpigmented_axis = excluded.pigmented_nonpigmented_axis;

insert into public.product_categories (
  code,
  name,
  icon_key,
  default_order,
  is_required,
  is_selectable
)
values
  ('CLEANSING_FOAM_GEL', '클렌징폼/젤', 'cleansing_foam', 10, true, true),
  ('CLEANSING_OIL_BALM', '클렌징오일/밤', 'cleansing_oil', 20, false, true),
  ('EXFOLIATOR', '필링&스크럽', 'exfoliator', 30, false, true),
  ('CLEANSING_WATER_MILK', '클렌징워터/밀크', 'cleansing_water', 40, false, true),
  ('SKIN_TONER', '스킨/토너', 'toner', 50, false, true),
  ('ESSENCE_SERUM_AMPOULE', '에센스/세럼/앰플', 'serum', 60, false, true),
  ('LOTION', '로션', 'lotion', 70, false, true),
  ('MIST_OIL', '미스트/오일', 'mist_oil', 80, false, true),
  ('CREAM', '크림', 'cream', 90, false, false),
  ('SUNSCREEN', '선크림', 'sunscreen', 100, false, false)
on conflict (code) do update
set
  name = excluded.name,
  icon_key = excluded.icon_key,
  default_order = excluded.default_order,
  is_required = excluded.is_required,
  is_selectable = excluded.is_selectable;

insert into public.products (
  category_id,
  brand,
  name,
  source,
  is_aac,
  is_verified,
  price_amount,
  currency
)
select
  category.id,
  'AAC',
  'AAC 세이프 BHA 세럼',
  'AAC_CATALOG',
  true,
  true,
  32000,
  'KRW'
from public.product_categories as category
where category.code = 'ESSENCE_SERUM_AMPOULE'
on conflict do nothing;

with upserted_code as (
  insert into public.diagnosis_codes (
    code_hash,
    code_hint,
    is_active
  )
  values (
    encode(extensions.digest('WHS-2026-1234', 'sha256'), 'hex'),
    'WHS-****-1234',
    true
  )
  on conflict (code_hash) do update
  set
    code_hint = excluded.code_hint,
    is_active = excluded.is_active
  returning id
)
insert into public.skin_diagnoses (
  diagnosis_code_id,
  skin_type_code,
  diagnosed_at,
  overall_summary
)
select
  upserted_code.id,
  'OSP',
  timestamptz '2026-08-15 09:30:00+09',
  '지성·민감성·색소성 피부로 피지, 자극 민감도, 색소 고민을 함께 관리하는 루틴이 필요합니다.'
from upserted_code
on conflict (diagnosis_code_id, diagnosed_at) do update
set
  skin_type_code = excluded.skin_type_code,
  overall_summary = excluded.overall_summary;

insert into public.diagnosis_axes (
  diagnosis_id,
  axis_code,
  selected_value,
  score
)
select
  diagnosis.id,
  axis.axis_code,
  axis.selected_value,
  axis.score
from public.skin_diagnoses as diagnosis
cross join (
  values
    ('O_D', 'O', 72.00::numeric),
    ('S_R', 'S', 66.00::numeric),
    ('P_N', 'P', 61.00::numeric)
) as axis(axis_code, selected_value, score)
where diagnosis.diagnosis_code_id = (
  select id
  from public.diagnosis_codes
  where code_hash = encode(extensions.digest('WHS-2026-1234', 'sha256'), 'hex')
)
and diagnosis.diagnosed_at = timestamptz '2026-08-15 09:30:00+09'
on conflict (diagnosis_id, axis_code) do update
set
  selected_value = excluded.selected_value,
  score = excluded.score;

insert into public.diagnosis_metrics (
  diagnosis_id,
  metric_code,
  metric_name,
  score,
  reference_score,
  level,
  display_order
)
select
  diagnosis.id,
  metric.metric_code,
  metric.metric_name,
  metric.score,
  metric.reference_score,
  metric.level,
  metric.display_order
from public.skin_diagnoses as diagnosis
cross join (
  values
    ('PORE', '모공', 79.00::numeric, 44.00::numeric, 'CAUTION', 10),
    ('BLACKHEAD', '블랙헤드', 61.00::numeric, 56.00::numeric, 'NORMAL', 20),
    ('GLOW', '광채', 86.00::numeric, 77.00::numeric, 'GOOD', 30),
    ('REDNESS', '홍조', 91.00::numeric, 75.00::numeric, 'HIGH', 40),
    ('DARK_CIRCLE', '다크서클', 89.00::numeric, 98.00::numeric, 'CAUTION', 50),
    ('ACNE', '여드름', 86.00::numeric, 89.00::numeric, 'CAUTION', 60)
) as metric(metric_code, metric_name, score, reference_score, level, display_order)
where diagnosis.diagnosis_code_id = (
  select id
  from public.diagnosis_codes
  where code_hash = encode(extensions.digest('WHS-2026-1234', 'sha256'), 'hex')
)
and diagnosis.diagnosed_at = timestamptz '2026-08-15 09:30:00+09'
on conflict (diagnosis_id, metric_code) do update
set
  metric_name = excluded.metric_name,
  score = excluded.score,
  reference_score = excluded.reference_score,
  level = excluded.level,
  display_order = excluded.display_order;
