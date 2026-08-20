# Well Less Supabase database

Project ref: `rzjhalgyhznynhyxpuoz`

## Applied migrations

1. `20260820122107_create_well_less_schema.sql`
   - 25 application tables
   - foreign keys, checks, indexes, updated-at triggers
   - RLS enabled on every application table
   - `anon` and `authenticated` table access revoked
2. `20260820122120_seed_well_less_reference_data.sql`
   - product categories and currently displayed skin types
   - demo diagnosis for personal code `WHS-2026-1234`
   - one AAC catalog product
   - three Storage buckets

## Access model

- Supabase Auth users are not used by the app.
- The Flutter app sends the personal code to FastAPI.
- FastAPI verifies the SHA-256 code hash and issues a short-lived application session.
- Only the backend may use the Supabase secret/service-role key.
- Never put the secret/service-role key or the OpenAI API key in Flutter.

## Storage

| Bucket | Public | Purpose |
| --- | --- | --- |
| `product-scans-original` | No | Camera originals, 1-3 images per product |
| `product-scans-cutout` | No | Background-removed PNG/WebP images |
| `product-catalog` | Yes | AAC catalog images |

## Common CLI commands

```powershell
npx supabase migration list
npx supabase db push
```

The remote project already has both migrations applied. Team members should not
run the SQL manually in the Dashboard; use migrations for future schema changes.
