from app.core.config import settings
from app.services.supabase_client import get_supabase_admin_client


def upload_product_scan(*, bucket: str, object_path: str, content: bytes, mime_type: str) -> None:
    """Upload when Supabase admin credentials exist; otherwise keep metadata-only demo mode."""
    if not settings.has_supabase_config:
        return
    get_supabase_admin_client().storage.from_(bucket).upload(
        path=object_path,
        file=content,
        file_options={"content-type": mime_type, "upsert": "false"},
    )
