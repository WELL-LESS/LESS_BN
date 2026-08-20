alter table public.ai_analysis_runs
  add column provider_prompt_id text,
  add column provider_prompt_version text;

comment on column public.ai_analysis_runs.provider_prompt_id is
  'OpenAI platform reusable prompt ID; not a secret.';
comment on column public.ai_analysis_runs.provider_prompt_version is
  'Pinned OpenAI platform prompt version used for reproducibility.';
