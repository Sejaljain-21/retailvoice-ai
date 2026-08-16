"""Customer order endpoints - the transactional side the agent operates on."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, Pagination
from app.core.exceptions import ConflictError, NotFoundError, PermissionError_
from app.models.enums import UserRole
from app.models.order import Order
from app.schemas.common import Page
from app.schemas.order import (
    CancelOrderRequest,
    CreateOrderRequest,
    CreateReturnRequest,
    OrderOut,
    ReturnRequestOut,
)
from app.services import orders_service as orders

router = APIRouter()


def _assert_can_view(user, order: Order) -> None:
    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)
    if not is_staff and order.customer_id != user.id:
        raise PermissionError_("You can only view your own orders.")


@router.get("", response_model=Page[OrderOut])
async def list_my_orders(
    user: CurrentUser,
    db: DbSession,
    page: Pagination,
    status_filter: str | None = Query(None, alias="status"),
    all_customers: bool = Query(False, description="Staff only: list every customer's orders"),
) -> Page[OrderOut]:
    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)
    customer_id = None if (all_customers and is_staff) else user.id

    rows = await orders.list_orders(
        db, customer_id=customer_id, status=status_filter,
        limit=page.page_size, offset=page.offset,
    )
    count_stmt = select(func.count(Order.id))
    if customer_id:
        count_stmt = count_stmt.where(Order.customer_id == customer_id)
    if status_filter:
        count_stmt = count_stmt.where(Order.status == status_filter)
    total = int((await db.execute(count_stmt)).scalar_one())

    return Page[OrderOut](
        items=[OrderOut.model_validate(o) for o in rows],
        total=total, page=page.page, page_size=page.page_size,
    )


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: CreateOrderRequest, user: CurrentUser, db: DbSession) -> OrderOut:
    created = await orders.create_order(
        db,
        customer=user,
        lines=[(line.product_id, line.quantity) for line in payload.items],
        shipping_address=payload.shipping_address,
        shipping_city=payload.shipping_city,
        shipping_pincode=payload.shipping_pincode,
        payment_method=payload.payment_method,
        coupon_code=payload.coupon_code,
    )
    # Re-read through the eager-loading query so serialising `shipment` and
    # `returns` never triggers a lazy load on the async session.
    order = await orders.get_order(db, created.id)
    return OrderOut.model_validate(order)


@router.get("/{reference}", response_model=OrderOut)
async def get_order(reference: str, user: CurrentUser, db: DbSession) -> OrderOut:
    """`reference` accepts either the internal id or the ORD-… order number."""
    order = await orders.get_order(db, reference) or await orders.get_order_by_number(db, reference)
    if not order:
        raise NotFoundError("Order not found.")
    _assert_can_view(user, order)
    return OrderOut.model_validate(order)


@router.post("/{reference}/cancel", response_model=OrderOut)
async def cancel_order(
    reference: str, payload: CancelOrderRequest, user: CurrentUser, db: DbSession
) -> OrderOut:
    order = await orders.get_order(db, reference) or await orders.get_order_by_number(db, reference)
    if not order:
        raise NotFoundError("Order not found.")
    _assert_can_view(user, order)

    result = await orders.cancel_order(db, order, payload.reason)
    if not result.get("success"):
        raise ConflictError(result.get("message", "This order cannot be cancelled."))
    return OrderOut.model_validate(await orders.get_order(db, order.id))


@router.post("/{reference}/returns", response_model=ReturnRequestOut,
             status_code=status.HTTP_201_CREATED)
async def create_return(
    reference: str, payload: CreateReturnRequest, user: CurrentUser, db: DbSession
) -> ReturnRequestOut:
    order = await orders.get_order(db, reference) or await orders.get_order_by_number(db, reference)
    if not order:
        raise NotFoundError("Order not found.")
    _assert_can_view(user, order)

    result = await orders.create_return(
        db, order=order, reason=payload.reason,
        comments=payload.comments, order_item_id=payload.order_item_id,
    )
    if not result.get("success"):
        raise ConflictError(result.get("message", "A return could not be created."))

    refreshed = await orders.get_order(db, order.id)
    rma = next(r for r in refreshed.returns if r.rma_number == result["rma_number"])
    return ReturnRequestOut.model_validate(rma)


@router.get("/{reference}/tracking")
async def track(reference: str, user: CurrentUser, db: DbSession) -> dict:
    order = await orders.get_order(db, reference) or await orders.get_order_by_number(db, reference)
    if not order:
        raise NotFoundError("Order not found.")
    _assert_can_view(user, order)
    return orders.shipment_snapshot(order)
