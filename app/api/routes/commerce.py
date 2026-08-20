from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.dependencies import SessionDependency
from app.schemas.api import CartQuantityRequest, OrderCreateRequest
from app.services.store import store

cart_router = APIRouter()
order_router = APIRouter()


@cart_router.get("")
async def get_cart(session: SessionDependency) -> dict:
    store.record_event(session, "cart_viewed", {})
    return {"data": store.cart(session)}


@cart_router.patch("/items/{item_id}")
async def update_cart_item(
    item_id: str,
    payload: CartQuantityRequest,
    session: SessionDependency,
) -> dict:
    return {"data": store.update_cart_item(session, item_id, payload.quantity)}


@cart_router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart_item(item_id: str, session: SessionDependency) -> Response:
    store.delete_cart_item(session, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@order_router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    session: SessionDependency,
    _idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    return {
        "data": store.create_order(
            session,
            payload.payment_method.value,
            payload.return_url,
        )
    }


@order_router.get("/{order_id}")
async def get_order(order_id: str, session: SessionDependency) -> dict:
    return {"data": store.get_order(session, order_id)}
