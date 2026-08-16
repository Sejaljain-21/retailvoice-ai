"""Catalogue schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None


class ProductOut(ORMModel):
    id: str
    sku: str
    name: str
    brand: str
    description: str
    price: float
    mrp: float
    currency: str
    stock_quantity: int
    is_active: bool
    rating: float
    review_count: int
    image_url: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    return_window_days: int
    is_returnable: bool
    category: CategoryOut | None = None

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.stock_quantity > 0


class ProductSearchQuery(BaseModel):
    q: str | None = None
    category: str | None = None
    brand: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    in_stock_only: bool = False
    sort: str = Field("relevance", pattern="^(relevance|price_asc|price_desc|rating|newest)$")


class StoreLocationOut(ORMModel):
    id: str
    name: str
    address: str
    city: str
    pincode: str
    phone: str | None = None
    opening_hours: str
    supports_pickup: bool
