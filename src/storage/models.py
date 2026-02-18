"""Database models for product tracking"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Boolean,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Product(Base):
    """Master product table - deduplicated across sources"""

    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_score_active_updated", "composite_score", "is_active", "last_updated_at"),
    )

    id = Column(Integer, primary_key=True)
    canonical_name = Column(String, index=True)  # Normalized product name
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
    alerts = relationship("Alert", back_populates="product")
    supplier_matches = relationship("SupplierMatch", back_populates="product")


class ProductObservation(Base):
    """Time-series observations of a product from various sources"""

    __tablename__ = "product_observations"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_product_id",
            "observed_at",
            name="uq_observation_source_product_time",
        ),
        Index("idx_observation_product_source_time", "product_id", "source", "observed_at"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    source = Column(String, index=True)  # tiktok_cc, tiktok_shop, aliexpress, etc.
    source_product_id = Column(String)  # ID in the source system

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

    product = relationship("Product", back_populates="observations")


class SupplierMatch(Base):
    """Matched supplier data from AliExpress/1688"""

    __tablename__ = "supplier_matches"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "supplier_source",
            "supplier_url",
            name="uq_supplier_match_per_product_source_url",
        ),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)

    supplier_source = Column(String)  # aliexpress, 1688
    supplier_url = Column(Text)
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

    product = relationship("Product", back_populates="supplier_matches")


class CreatorTracking(Base):
    """Track creators promoting specific products (saturation metric)"""

    __tablename__ = "creator_tracking"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)

    creator_username = Column(String)
    creator_followers = Column(Integer)
    video_url = Column(Text)
    video_views = Column(Integer)
    video_posted_at = Column(DateTime)

    observed_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Alerts sent for high-scoring products"""

    __tablename__ = "alerts"
    __table_args__ = (Index("idx_alerts_product_sent", "product_id", "sent_at"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)

    alert_type = Column(String)  # new_trend, velocity_spike, margin_opportunity
    channel = Column(String)  # discord, email, webhook
    sent_at = Column(DateTime, default=datetime.utcnow)

    composite_score_at_alert = Column(Float)
    alert_data = Column(JSON)  # Full context sent with alert

    product = relationship("Product", back_populates="alerts")


class ScrapeJob(Base):
    """Track scraping jobs for monitoring and debugging"""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True)
    agent_name = Column(String, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String)  # running, completed, failed

    products_found = Column(Integer, default=0)
    errors = Column(JSON)
    duration_seconds = Column(Float)
