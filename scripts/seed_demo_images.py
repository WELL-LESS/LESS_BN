"""Upload the current Flutter demo images and register their DB metadata."""

from pathlib import Path

from app.services.supabase_client import get_supabase_admin_client

APP_ROOT = Path(__file__).resolve().parents[2] / "well_less_app"


def upload(bucket: str, object_path: str, source: Path, mime_type: str) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    get_supabase_admin_client().storage.from_(bucket).upload(
        path=object_path,
        file=source.read_bytes(),
        file_options={"content-type": mime_type, "upsert": "true"},
    )


def main() -> None:
    client = get_supabase_admin_client()

    catalog_source = APP_ROOT / "assets" / "images" / "aac_serum_bottle.png"
    catalog_path = "aac/aac-safe-bha-serum.png"
    upload("product-catalog", catalog_path, catalog_source, "image/png")
    (
        client.table("products")
        .update(
            {
                "image_bucket": "product-catalog",
                "image_path": catalog_path,
                "price_amount": 48000,
            }
        )
        .eq("brand", "AAC")
        .eq("is_aac", True)
        .execute()
    )

    diagnosis = (
        client.table("skin_diagnoses")
        .select("id")
        .order("diagnosed_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not diagnosis:
        raise RuntimeError("Seed diagnosis is missing; apply database migrations first.")

    diagnosis_source = APP_ROOT / "assets" / "images" / "skin_face_2.png"
    diagnosis_path = f"{diagnosis[0]['id']}/skin-face-2.png"
    upload("diagnosis-reports", diagnosis_path, diagnosis_source, "image/png")
    (
        client.table("diagnosis_images")
        .upsert(
            {
                "diagnosis_id": diagnosis[0]["id"],
                "image_role": "FACE",
                "bucket": "diagnosis-reports",
                "object_path": diagnosis_path,
                "mime_type": "image/png",
                "size_bytes": diagnosis_source.stat().st_size,
                "display_order": 1,
            },
            on_conflict="diagnosis_id,image_role,display_order",
        )
        .execute()
    )

    print("Uploaded product catalog and private diagnosis demo images.")


if __name__ == "__main__":
    main()
