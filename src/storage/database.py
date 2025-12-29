"""Database operations for TikTok Product Scout."""

import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Alert,
    Base,
    CreatorTracking,
    Product,
    ProductObservation,
    ScrapeJob,
    ScrapedProduct,
    SupplierMatch,
)


class Database:
    """Database manager for TikTok Product Scout."""

    def __init__(self, db_url: str = "sqlite:///data/db/products.db"):
        """Initialize database connection.

        Args:
            db_url: SQLAlchemy database URL
        """
        # Ensure database directory exists
        if db_url.startswith("sqlite:///"):
            db_path = Path(db_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    @contextmanager
    def session(self):
        """Get database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ========================================================================
    # Product Operations
    # ========================================================================

    def upsert_product(self, scraped_product: ScrapedProduct) -> Product:
        """Insert or update a product based on scraped data.

        Args:
            scraped_product: Scraped product data

        Returns:
            Product instance
        """
        with self.session() as session:
            # Find existing product
            existing = self._find_matching_product(session, scraped_product)

            if existing:
                product = existing
                product.last_updated_at = datetime.utcnow()
            else:
                product = Product(
                    canonical_name=self._normalize_name(scraped_product.name),
                    category=scraped_product.category,
                    first_seen_at=datetime.utcnow(),
                )
                session.add(product)
                session.flush()

            # Add observation
            observation = ProductObservation(
                product_id=product.id,
                source=scraped_product.source,
                source_product_id=scraped_product.source_id,
                observed_at=scraped_product.scraped_at,
                price_usd=scraped_product.price_usd,
                views=scraped_product.views,
                sales=scraped_product.sales,
                orders=scraped_product.orders,
                reviews=scraped_product.reviews,
                rating=scraped_product.rating,
                raw_data=scraped_product.raw_data,
            )

            # Calculate deltas from previous observation
            self._calculate_deltas(session, observation)

            session.add(observation)
            session.commit()
            session.refresh(product)

            return product

    def _find_matching_product(
        self, session: Session, scraped: ScrapedProduct
    ) -> Optional[Product]:
        """Find existing product that matches the scraped data."""
        normalized_name = self._normalize_name(scraped.name)

        # Exact match
        exact = (
            session.query(Product).filter(Product.canonical_name == normalized_name).first()
        )

        if exact:
            return exact

        # Fuzzy match - get candidates from same category
        if scraped.category:
            candidates = session.query(Product).filter(Product.category == scraped.category).all()

            for candidate in candidates:
                similarity = fuzz.ratio(normalized_name, candidate.canonical_name)
                if similarity > 85:  # 85% similarity threshold
                    return candidate

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize product name for matching."""
        name = name.lower().strip()
        name = re.sub(r"[^\w\s]", "", name)  # Remove punctuation
        name = re.sub(r"\s+", " ", name)  # Normalize whitespace
        return name

    def _calculate_deltas(self, session: Session, observation: ProductObservation):
        """Calculate change since last observation from same source."""
        previous = (
            session.query(ProductObservation)
            .filter(
                ProductObservation.product_id == observation.product_id,
                ProductObservation.source == observation.source,
                ProductObservation.observed_at < observation.observed_at,
            )
            .order_by(ProductObservation.observed_at.desc())
            .first()
        )

        if previous:
            if observation.views is not None and previous.views is not None:
                observation.views_delta = observation.views - previous.views
            if observation.sales is not None and previous.sales is not None:
                observation.sales_delta = observation.sales - previous.sales

    def get_product(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        with self.session() as session:
            return session.query(Product).filter(Product.id == product_id).first()

    def get_products_for_scoring(self, min_observations: int = 2) -> List[Product]:
        """Get products with enough data for meaningful scoring."""
        with self.session() as session:
            products = (
                session.query(Product)
                .join(ProductObservation)
                .group_by(Product.id)
                .having(func.count(ProductObservation.id) >= min_observations)
                .all()
            )
            # Detach from session
            session.expunge_all()
            return products

    def query_products(
        self,
        min_score: float = 0,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Product]:
        """Query products with filters."""
        with self.session() as session:
            query = session.query(Product).filter(Product.composite_score >= min_score)

            if category:
                query = query.filter(Product.category == category)

            query = query.order_by(Product.composite_score.desc())
            products = query.limit(limit).offset(offset).all()

            # Detach from session
            session.expunge_all()
            return products

    def update_product_scores(
        self,
        product_id: int,
        composite_score: float,
        velocity_score: float,
        margin_score: float,
        saturation_score: float,
    ):
        """Update product scores."""
        with self.session() as session:
            product = session.query(Product).filter(Product.id == product_id).first()
            if product:
                product.composite_score = composite_score
                product.velocity_score = velocity_score
                product.margin_score = margin_score
                product.saturation_score = saturation_score
                product.last_updated_at = datetime.utcnow()

    # ========================================================================
    # Observation Operations
    # ========================================================================

    def get_observations(
        self, product_id: int, limit: Optional[int] = None
    ) -> List[ProductObservation]:
        """Get observations for a product."""
        with self.session() as session:
            query = (
                session.query(ProductObservation)
                .filter(ProductObservation.product_id == product_id)
                .order_by(ProductObservation.observed_at.desc())
            )

            if limit:
                query = query.limit(limit)

            observations = query.all()
            # Detach from session
            session.expunge_all()
            return observations

    # ========================================================================
    # Supplier Operations
    # ========================================================================

    def save_supplier_match(self, product_id: int, supplier_data: Dict):
        """Save supplier match data."""
        with self.session() as session:
            supplier_match = SupplierMatch(
                product_id=product_id,
                supplier_source=supplier_data.get("source", "aliexpress"),
                supplier_url=supplier_data.get("url", ""),
                supplier_price_usd=supplier_data.get("min_price"),
                shipping_cost_usd=supplier_data.get("shipping_estimate"),
                estimated_delivery_days=supplier_data.get("delivery_days"),
                supplier_rating=supplier_data.get("supplier_rating"),
                supplier_orders=supplier_data.get("supplier_orders"),
                confidence_score=supplier_data.get("confidence", 0.5),
            )
            session.add(supplier_match)

    def get_supplier_data(self, product_id: int) -> Optional[Dict]:
        """Get supplier data for a product."""
        with self.session() as session:
            supplier = (
                session.query(SupplierMatch)
                .filter(SupplierMatch.product_id == product_id)
                .order_by(SupplierMatch.matched_at.desc())
                .first()
            )

            if not supplier:
                return None

            return {
                "source": supplier.supplier_source,
                "url": supplier.supplier_url,
                "min_price": supplier.supplier_price_usd,
                "shipping_estimate": supplier.shipping_cost_usd,
                "delivery_days": supplier.estimated_delivery_days,
                "supplier_rating": supplier.supplier_rating,
                "supplier_orders": supplier.supplier_orders,
            }

    def get_products_needing_suppliers(self, limit: int = 50) -> List[Product]:
        """Get products that need supplier matching."""
        with self.session() as session:
            # Get products without recent supplier matches
            cutoff = datetime.utcnow() - timedelta(days=7)

            products = (
                session.query(Product)
                .outerjoin(SupplierMatch)
                .filter(
                    (SupplierMatch.id.is_(None))
                    | (SupplierMatch.matched_at < cutoff)
                )
                .limit(limit)
                .all()
            )

            # Detach from session
            session.expunge_all()
            return products

    # ========================================================================
    # Alert Operations
    # ========================================================================

    def record_alert(self, product_id: int, score_data: Dict):
        """Record that an alert was sent."""
        with self.session() as session:
            alert = Alert(
                product_id=product_id,
                alert_type=score_data.get("recommendation", "opportunity"),
                channel="discord",  # Default channel
                composite_score_at_alert=score_data.get("composite_score", 0),
                alert_data=score_data,
            )
            session.add(alert)

            # Mark product as alerted
            product = session.query(Product).filter(Product.id == product_id).first()
            if product:
                product.is_alerted = True

    def get_alert_candidates(
        self, min_score: float = 70, cooldown_hours: int = 24
    ) -> List[Product]:
        """Get products eligible for alerts."""
        with self.session() as session:
            cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)

            products = (
                session.query(Product)
                .outerjoin(Alert)
                .filter(
                    Product.composite_score >= min_score,
                    Product.is_active == True,
                    (Alert.id.is_(None)) | (Alert.sent_at < cutoff),
                )
                .group_by(Product.id)
                .all()
            )

            # Detach from session
            session.expunge_all()
            return products

    # ========================================================================
    # Statistics Operations
    # ========================================================================

    def count_products(self) -> int:
        """Count total products."""
        with self.session() as session:
            return session.query(Product).count()

    def count_by_recommendation(self) -> Dict[str, int]:
        """Count products by recommendation tier (based on score)."""
        with self.session() as session:
            products = session.query(Product).all()

            counts = {
                "strong_buy": 0,
                "buy": 0,
                "watch": 0,
                "pass": 0,
                "too_late": 0,
            }

            for product in products:
                score = product.composite_score
                if score >= 80:
                    counts["strong_buy"] += 1
                elif score >= 65:
                    counts["buy"] += 1
                elif score >= 50:
                    counts["watch"] += 1
                elif score >= 35:
                    counts["pass"] += 1
                else:
                    counts["too_late"] += 1

            return counts

    def count_by_category(self) -> Dict[str, int]:
        """Count products by category."""
        with self.session() as session:
            results = (
                session.query(Product.category, func.count(Product.id))
                .group_by(Product.category)
                .all()
            )
            return {category or "Unknown": count for category, count in results}

    def count_observations_today(self) -> int:
        """Count observations added today."""
        with self.session() as session:
            today = datetime.utcnow().date()
            return (
                session.query(ProductObservation)
                .filter(func.date(ProductObservation.observed_at) == today)
                .count()
            )

    def count_alerts_today(self) -> int:
        """Count alerts sent today."""
        with self.session() as session:
            today = datetime.utcnow().date()
            return session.query(Alert).filter(func.date(Alert.sent_at) == today).count()

    def get_last_scrape_time(self) -> Optional[datetime]:
        """Get timestamp of last successful scrape."""
        with self.session() as session:
            job = (
                session.query(ScrapeJob)
                .filter(ScrapeJob.status == "completed")
                .order_by(ScrapeJob.completed_at.desc())
                .first()
            )
            return job.completed_at if job else None

    # ========================================================================
    # Cleanup Operations
    # ========================================================================

    def cleanup_old_observations(self, cutoff_date: datetime) -> int:
        """Delete observations older than cutoff date."""
        with self.session() as session:
            deleted = (
                session.query(ProductObservation)
                .filter(ProductObservation.observed_at < cutoff_date)
                .delete()
            )
            return deleted
