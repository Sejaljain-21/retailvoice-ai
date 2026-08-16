"""Product catalogue and inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.order import OrderItem


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(64))

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)

    price: Mapped[float] = mapped_column(Float, nullable=False)
    mrp: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(4), default="INR")

    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str | None] = mapped_column(String(512))

    # e.g. {"colour": "Midnight Black", "warranty_months": 12, "size": "M"}
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    return_window_days: Mapped[int] = mapped_column(Integer, default=7)
    is_returnable: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped["Category | None"] = relationship(back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.stock_quantity > 0

    @property
    def discount_percent(self) -> int:
        if self.mrp <= 0 or self.price >= self.mrp:
            return 0
        return round((self.mrp - self.price) / self.mrp * 100)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.sku} {self.name!r}>"


class StoreLocation(UUIDMixin, TimestampMixin, Base):
    """Physical retail stores - used for 'nearest store' and click-and-collect."""

    __tablename__ = "store_locations"

    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(80), index=True)
    pincode: Mapped[str] = mapped_column(String(16), index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    opening_hours: Mapped[str] = mapped_column(String(120), default="10:00 - 21:00")
    supports_pickup: Mapped[bool] = mapped_column(Boolean, default=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
