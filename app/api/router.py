from fastapi import APIRouter

from app.api.routes import (
    analytics,
    auth,
    commerce,
    diagnoses,
    health,
    integrations,
    jobs,
    me,
    products,
    routines,
    skin_types,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(me.router, prefix="/me", tags=["home"])
api_router.include_router(diagnoses.router, prefix="/diagnoses", tags=["diagnoses"])
api_router.include_router(skin_types.router, prefix="/skin-types", tags=["diagnoses"])
api_router.include_router(products.router, prefix="/product-categories", tags=["products"])
api_router.include_router(routines.router, prefix="/routines", tags=["routines"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(commerce.cart_router, prefix="/cart", tags=["cart"])
api_router.include_router(commerce.order_router, prefix="/orders", tags=["orders"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
