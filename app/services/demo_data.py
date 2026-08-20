from app.schemas.diagnosis import DiagnosisResponse

DEMO_PERSONAL_CODE = "AAC2026"

DEMO_DIAGNOSIS = DiagnosisResponse(
    id="demo-diagnosis",
    skin_type="DRY_SENSITIVE",
    concerns=["SENSITIVITY", "DEHYDRATION"],
    recommended_ingredients=["ceramide", "panthenol", "hyaluronic acid"],
    caution_ingredients=["fragrance", "denatured alcohol"],
)

AAC_REPLACEMENTS = {
    "TONER": "aac-toner-001",
    "SERUM": "aac-serum-001",
    "CREAM": "aac-cream-001",
}
