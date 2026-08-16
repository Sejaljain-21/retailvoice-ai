"""Storefront catalogue: categories, products, search and store locator."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, Pagination
from app.core.exceptions import NotFoundError
from app.models.catalog import Category, Product, StoreLocation
from app.schemas.catalog import CategoryOut, ProductOut, StoreLocationOut
from app.schemas.common import Page

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(db: DbSession) -> list[CategoryOut]:
    rows = (await db.execute(select(Category).order_by(Category.name))).scalars().all()
    return [CategoryOut.model_validate(c) for c in rows]


@router.get("/products", response_model=Page[ProductOut])
async def list_products(
    db: DbSession,
    page: Pagination,
    q: str | None = Query(None, description="Free-text search across name, brand, description"),
    category: str | None = Query(None, description="Category slug"),
    brand: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock_only: bool = False,
    sort: str = Query("relevance", pattern="^(relevance|price_asc|price_desc|rating|newest)$"),
) -> Page[ProductOut]:
    stmt = select(Product).options(selectinload(Product.category)).where(Product.is_active.is_(True))
    count_stmt = select(func.count(Product.id)).where(Product.is_active.is_(True))

    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(Product.name.ilike(like), Product.brand.ilike(like),
                Product.description.ilike(like))
        )
    if category:
        sub = select(Category.id).where(Category.slug == category)
        filters.append(Product.category_id.in_(sub))
    if brand:
        filters.append(Product.brand.ilike(f"%{brand}%"))
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    if in_stock_only:
        filters.append(Product.stock_quantity > 0)

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    order = {
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "rating": Product.rating.desc(),
        "newest": Product.created_at.desc(),
    }.get(sort, Product.rating.desc())
    stmt = stmt.order_by(order).limit(page.page_size).offset(page.offset)

    rows = (await db.execute(stmt)).scalars().all()
    total = int((await db.execute(count_stmt)).scalar_one())

    return Page[ProductOut](
        items=[ProductOut.model_validate(p) for p in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: DbSession) -> ProductOut:
    product = (
        await db.execute(
            select(Product)
            .options(selectinload(Product.category))
            .where(or_(Product.id == product_id, Product.sku == product_id))
        )
    ).scalars().first()
    if not product:
        raise NotFoundError("That product does not exist.")
    return ProductOut.model_validate(product)


@router.get("/stores", response_model=list[StoreLocationOut])
async def list_stores(
    db: DbSession,
    city: str | None = None,
    pincode: str | None = None,
) -> list[StoreLocationOut]:
    stmt = select(StoreLocation)
    if city:
        stmt = stmt.where(StoreLocation.city.ilike(f"%{city}%"))
    if pincode:
        stmt = stmt.where(StoreLocation.pincode == pincode)
    rows = (await db.execute(stmt.order_by(StoreLocation.city))).scalars().all()
    return [StoreLocationOut.model_validate(s) for s in rows]
