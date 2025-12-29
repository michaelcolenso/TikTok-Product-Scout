"""Database operations and management"""

import re
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from rapidfuzz import fuzz
import logging

from .models import Base, Product, ProductObservation, SupplierMatch, Alert, ScrapeJob
from ..agents.base_agent import ScrapedProduct

logger = logging.getLogger(__name__)


class Database:
    """Database management class"""

    def __init__(self, db_url: str = "sqlite:///data/db/products.db"):
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized: {db_url}")

    @contextmanager
    def session(self):
        """Context manager for database sessions"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def upsert_product(self, scraped_product: ScrapedProduct) -> Product:
        """
        Insert or update a product based on scraped data.

        Deduplication strategy:
        1. Try exact name match
        2. Try fuzzy name match (similarity > 85%)
        3. Create new product if no match
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
                session.flush()  # Get the ID

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
            logger.debug(f"Upserted product: {product.canonical_name} (ID: {product.id})")

            return product

    def _find_matching_product(
        self, session: Session, scraped: ScrapedProduct
    ) -> Optional[Product]:
        """Find existing product that matches the scraped data"""
        normalized_name = self._normalize_name(scraped.name)

        # Exact match
        exact = session.query(Product).filter(Product.canonical_name == normalized_name).first()

        if exact:
            return exact

        # Fuzzy match - get candidates from same category
        if scraped.category:
            candidates = session.query(Product).filter(Product.category == scraped.category).all()
        else:
            # If no category, check all products (more expensive)
            candidates = session.query(Product).limit(1000).all()

        for candidate in candidates:
            similarity = fuzz.ratio(normalized_name, candidate.canonical_name)
            if similarity > 85:  # 85% similarity threshold
                logger.debug(
                    f"Fuzzy match found: {normalized_name} -> {candidate.canonical_name} ({similarity}%)"
                )
                return candidate

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize product name for matching"""
        name = name.lower().strip()
        name = re.sub(r"[^\w\s]", "", name)  # Remove punctuation
        name = re.sub(r"\s+", " ", name)  # Normalize whitespace
        return name

    def _calculate_deltas(self, session: Session, observation: ProductObservation):
        """Calculate change since last observation from same source"""
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
            if observation.views and previous.views:
                observation.views_delta = observation.views - previous.views
            if observation.sales and previous.sales:
                observation.sales_delta = observation.sales - previous.sales

    def get_products_for_scoring(self, min_observations: int = 2) -> list[Product]:
        """Get products with enough data for meaningful scoring"""
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

    def get_product(self, product_id: int) -> Optional[Product]:
        """Get a single product by ID"""
        with self.session() as session:
            product = session.query(Product).filter(Product.id == product_id).first()
            if product:
                session.expunge(product)
            return product

    def get_observations(
        self, product_id: int, limit: Optional[int] = None
    ) -> list[ProductObservation]:
        """Get observations for a product"""
        with self.session() as session:
            query = (
                session.query(ProductObservation)
                .filter(ProductObservation.product_id == product_id)
                .order_by(ProductObservation.observed_at.desc())
            )

            if limit:
                query = query.limit(limit)

            observations = query.all()
            session.expunge_all()
            return observations

    def get_supplier_data(self, product_id: int) -> Optional[dict]:
        """Get supplier match data for a product"""
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
                "min_price": supplier.supplier_price_usd,
                "shipping_estimate": supplier.shipping_cost_usd or 0,
                "delivery_days": supplier.estimated_delivery_days,
                "supplier_url": supplier.supplier_url,
                "supplier_rating": supplier.supplier_rating,
            }

    def update_product_scores(
        self,
        product_id: int,
        composite_score: float,
        velocity_score: float,
        margin_score: float,
        saturation_score: float,
    ):
        """Update product scores"""
        with self.session() as session:
            product = session.query(Product).filter(Product.id == product_id).first()
            if product:
                product.composite_score = composite_score
                product.velocity_score = velocity_score
                product.margin_score = margin_score
                product.saturation_score = saturation_score
                product.last_updated_at = datetime.utcnow()

    def get_alert_candidates(
        self, min_score: float = 70, cooldown_hours: int = 24
    ) -> list[Product]:
        """Get products that should trigger alerts"""
        cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)

        with self.session() as session:
            # Products with high scores that haven't been alerted recently
            products = (
                session.query(Product)
                .filter(Product.composite_score >= min_score, Product.is_active == True)
                .outerjoin(Alert)
                .group_by(Product.id)
                .having(func.max(Alert.sent_at) < cutoff or func.max(Alert.sent_at).is_(None))
                .all()
            )

            session.expunge_all()
            return products

    def record_alert(self, product_id: int, score_data: dict):
        """Record that an alert was sent"""
        with self.session() as session:
            alert = Alert(
                product_id=product_id,
                alert_type="opportunity",
                channel="discord",
                composite_score_at_alert=score_data.get("composite_score", 0),
                alert_data=score_data,
            )
            session.add(alert)

            # Mark product as alerted
            product = session.query(Product).filter(Product.id == product_id).first()
            if product:
                product.is_alerted = True

    def query_products(
        self,
        min_score: float = 0,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Query products with filters"""
        with self.session() as session:
            query = session.query(Product).filter(Product.composite_score >= min_score)

            if category:
                query = query.filter(Product.category == category)

            query = query.order_by(Product.composite_score.desc()).limit(limit).offset(offset)

            products = query.all()
            session.expunge_all()
            return products

    def count_products(self) -> int:
        """Count total products"""
        with self.session() as session:
            return session.query(Product).count()

    def get_products_needing_suppliers(self, limit: int = 50) -> list[Product]:
        """Get products that don't have supplier data yet"""
        with self.session() as session:
            products = (
                session.query(Product)
                .outerjoin(SupplierMatch)
                .filter(SupplierMatch.id.is_(None))
                .limit(limit)
                .all()
            )

            session.expunge_all()
            return products

    def save_supplier_match(self, product_id: int, supplier_data: dict):
        """Save supplier match data"""
        with self.session() as session:
            match = SupplierMatch(
                product_id=product_id,
                supplier_source=supplier_data.get("source", "aliexpress"),
                supplier_url=supplier_data.get("supplier_url", ""),
                supplier_price_usd=supplier_data.get("min_price", 0),
                shipping_cost_usd=supplier_data.get("shipping_estimate", 0),
                estimated_delivery_days=supplier_data.get("delivery_days", 0),
                supplier_rating=supplier_data.get("supplier_rating", 0),
                supplier_orders=supplier_data.get("supplier_orders", 0),
                confidence_score=supplier_data.get("confidence", 0.5),
            )
            session.add(match)

    def cleanup_old_observations(self, cutoff: datetime) -> int:
        """Remove observations older than cutoff date"""
        with self.session() as session:
            deleted = (
                session.query(ProductObservation)
                .filter(ProductObservation.observed_at < cutoff)
                .delete()
            )
            logger.info(f"Deleted {deleted} old observations")
            return deleted

    def record_scrape_job(
        self, agent_name: str, status: str, products_found: int = 0, duration: float = 0
    ):
        """Record a scrape job completion"""
        with self.session() as session:
            job = ScrapeJob(
                agent_name=agent_name,
                status=status,
                products_found=products_found,
                duration_seconds=duration,
                completed_at=datetime.utcnow() if status == "completed" else None,
            )
            session.add(job)
