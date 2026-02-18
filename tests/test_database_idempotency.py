from datetime import datetime

from src.agents.base_agent import ScrapedProduct
from src.storage import Database
from src.storage.models import ProductObservation, SupplierMatch


def test_upsert_product_is_idempotent_for_same_source_observation():
    db = Database("sqlite:///:memory:")
    scraped_at = datetime(2025, 1, 1, 10, 0, 0)

    payload = ScrapedProduct(
        source="tiktok_cc",
        source_id="abc123",
        name="Portable Blender",
        category="Home",
        price_usd=19.99,
        product_url="https://example.test/product",
        views=1000,
        sales=25,
        scraped_at=scraped_at,
    )

    db.upsert_product(payload)
    db.upsert_product(payload)

    with db.session() as session:
        assert session.query(ProductObservation).count() == 1


def test_save_supplier_match_updates_existing_unique_record():
    db = Database("sqlite:///:memory:")
    product = ScrapedProduct(
        source="tiktok_cc",
        source_id="xyz456",
        name="LED Face Mask",
        category="Beauty",
        price_usd=29.99,
        product_url="https://example.test/product2",
        scraped_at=datetime(2025, 1, 1, 11, 0, 0),
    )

    db.upsert_product(product)
    product_id = db.query_products(limit=1)[0].id

    db.save_supplier_match(
        product_id,
        {
            "source": "aliexpress",
            "supplier_url": "https://supplier.test/item",
            "min_price": 8.0,
            "shipping_estimate": 2.0,
        },
    )
    db.save_supplier_match(
        product_id,
        {
            "source": "aliexpress",
            "supplier_url": "https://supplier.test/item",
            "min_price": 7.5,
            "shipping_estimate": 2.5,
        },
    )

    with db.session() as session:
        assert session.query(SupplierMatch).count() == 1
        match = session.query(SupplierMatch).first()
        assert match.supplier_price_usd == 7.5
        assert match.shipping_cost_usd == 2.5
