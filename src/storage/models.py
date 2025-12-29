"""Database models for TikTok Product Scout."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================================================
# Pydantic Models (for data transfer)
# ============================================================================


class ScrapedProduct(BaseModel):
    """Normalized product data from any source."""

    source: str  # e.g., "tiktok_cc", "aliexpress"
    source_id: str  # Unique ID from source
    name: str
    category: Optional[str] = None
    price_usd: Optional[float] = None
    image_url: Optional[str] = None
    product_url: str

    # Source-specific metrics (nullable)
    views: Optional[int] = None
    sales: Optional[int] = None
    orders: Optional[int] = None
    reviews: Optional[int] = None
    rating: Optional[float] = None

    # Temporal data
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    first_seen_at: Optional[datetime] = None

    # Raw data for debugging
    raw_data: Optional[dict] = None

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# SQLAlchemy Models (for database)
# ============================================================================


class Product(Base):
    """Master product table - deduplicated across sources."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String, index=True, nullable=False)
    category = Column(String, index=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Aggregated metrics (updated by scoring engine)
    composite_score = Column(Float, default=0.0, index=True)
    velocity_score = Column(Float, default=0.0)
    margin_score = Column(Float, default=0.0)
    saturation_score = Column(Float, default=0.0)

    # Status flags
    is_active = Column(Boolean, default=True)
    is_alerted = Column(Boolean, default=False)  # Already sent alert

    # Relationships
    observations = relationship("ProductObservation", back_populates="product")
    supplier_matches = relationship("SupplierMatch", back_populates="product")
    creator_tracking = relationship("CreatorTracking", back_populates="product")
    alerts = relationship("Alert", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.canonical_name}', score={self.composite_score})>"


class ProductObservation(Base):
    """Time-series observations of a product from various sources."""

    __tablename__ = "product_observations"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    source = Column(String, index=True, nullable=False)
    source_product_id = Column(String)

    observed_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Metrics (nullable - not all sources have all metrics)
    price_usd = Column(Float)
    views = Column(Integer)
    sales = Column(Integer)
    orders = Column(Integer)
    reviews = Column(Integer)
    rating = Column(Float)

    # Calculated metrics
    views_delta = Column(Integer)  # Change since last observation
    sales_delta = Column(Integer)

    # Raw data
    raw_data = Column(JSON)

    # Relationships
    product = relationship("Product", back_populates="observations")

    def __repr__(self):
        return f"<ProductObservation(id={self.id}, product_id={self.product_id}, source='{self.source}')>"


class SupplierMatch(Base):
    """Matched supplier data from AliExpress/1688."""

    __tablename__ = "supplier_matches"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)

    supplier_source = Column(String)  # aliexpress, 1688
    supplier_url = Column(String)
    supplier_price_usd = Column(Float)
    shipping_cost_usd = Column(Float)
    estimated_delivery_days = Column(Integer)
    supplier_rating = Column(Float)
    supplier_orders = Column(Integer)

    # Margin calculation
    estimated_margin_percent = Column(Float)
    estimated_margin_usd = Column(Float)

    matched_at = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Float)  # How confident is the product match

    # Relationships
    product = relationship("Product", back_populates="supplier_matches")

    def __repr__(self):
        return f"<SupplierMatch(id={self.id}, product_id={self.product_id}, source='{self.supplier_source}')>"


class CreatorTracking(Base):
    """Track creators promoting specific products (saturation metric)."""

    __tablename__ = "creator_tracking"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)

    creator_username = Column(String)
    creator_followers = Column(Integer)
    video_url = Column(String)
    video_views = Column(Integer)
    video_posted_at = Column(DateTime)

    observed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="creator_tracking")

    def __repr__(self):
        return f"<CreatorTracking(id={self.id}, creator='{self.creator_username}', product_id={self.product_id})>"


class Alert(Base):
    """Alerts sent for high-scoring products."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)

    alert_type = Column(String)  # new_trend, velocity_spike, margin_opportunity
    channel = Column(String)  # discord, email, webhook
    sent_at = Column(DateTime, default=datetime.utcnow)

    composite_score_at_alert = Column(Float)
    alert_data = Column(JSON)  # Full context sent with alert

    # Relationships
    product = relationship("Product", back_populates="alerts")

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', product_id={self.product_id})>"


class ScrapeJob(Base):
    """Track scraping jobs for monitoring and debugging."""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True)
    agent_name = Column(String, index=True, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String)  # running, completed, failed

    products_found = Column(Integer, default=0)
    errors = Column(JSON)
    duration_seconds = Column(Float)

    def __repr__(self):
        return f"<ScrapeJob(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"
