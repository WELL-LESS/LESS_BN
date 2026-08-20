from app.core.config import settings
from supabase import Client, create_client


def get_supabase_admin_client() -> Client:
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError("Supabase 서버 환경변수가 설정되지 않았습니다.")
    return create_client(settings.supabase_url, settings.supabase_secret_key)
