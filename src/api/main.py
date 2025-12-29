"""FastAPI application for TikTok Product Scout"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import logging

from ..storage import Database
from ..scoring import CompositeScorer
from ..utils.config import config

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TikTok Product Scout API",
    description="API for viral product discovery and scoring",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database and scorer
db = Database(config.database_url)
scorer = CompositeScorer()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "TikTok Product Scout API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/products")
async def list_products(
    min_score: float = Query(0, ge=0, le=100, description="Minimum composite score"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List products with optional filtering.

    - **min_score**: Minimum composite score (0-100)
    - **category**: Filter by product category
    - **limit**: Number of results (max 200)
    - **offset**: Pagination offset
    """
    try:
        products = db.query_products(
            min_score=min_score, category=category, limit=limit, offset=offset
        )

        results = []
        for product in products:
            results.append(
                {
                    "id": product.id,
                    "name": product.canonical_name,
                    "category": product.category,
                    "composite_score": product.composite_score,
                    "velocity_score": product.velocity_score,
                    "margin_score": product.margin_score,
                    "saturation_score": product.saturation_score,
                    "first_seen": product.first_seen_at.isoformat(),
                    "last_updated": product.last_updated_at.isoformat(),
                }
            )

        return {"products": results, "total": len(results), "offset": offset, "limit": limit}
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    """Get detailed product information including full scoring breakdown"""
    try:
        product = db.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        observations = db.get_observations(product_id)
        supplier_data = db.get_supplier_data(product_id)
        score = scorer.score_product(product, observations, supplier_data)

        return {
            "product": {
                "id": product.id,
                "name": product.canonical_name,
                "category": product.category,
                "first_seen": product.first_seen_at.isoformat(),
            },
            "score": {
                "composite": score.composite_score,
                "velocity": score.velocity_score,
                "margin": score.margin_score,
                "saturation": score.saturation_score,
                "confidence": score.confidence,
                "recommendation": score.recommendation,
                "signals": score.signals,
                "details": score.details,
            },
            "observations": [
                {
                    "source": o.source,
                    "observed_at": o.observed_at.isoformat(),
                    "price": o.price_usd,
                    "views": o.views,
                    "sales": o.sales,
                }
                for o in observations[-20:]  # Last 20 observations
            ],
            "supplier": supplier_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/opportunities")
async def get_opportunities(
    min_score: float = Query(65, ge=0, le=100, description="Minimum composite score"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
):
    """
    Get top opportunities ranked by composite score.
    Only returns products with actionable recommendations.
    """
    try:
        products = db.query_products(min_score=min_score, limit=limit)

        opportunities = []
        for product in products:
            observations = db.get_observations(product.id)
            supplier_data = db.get_supplier_data(product.id)
            score = scorer.score_product(product, observations, supplier_data)

            if score.recommendation in ["strong_buy", "buy", "watch"]:
                opportunities.append(
                    {
                        "product": {
                            "id": product.id,
                            "name": product.canonical_name,
                            "category": product.category,
                        },
                        "score": score.composite_score,
                        "recommendation": score.recommendation,
                        "signals": score.signals[:5],
                        "margin_estimate": (
                            score.details.get("margin", {}).get("net_margin_percent")
                            if score.details.get("margin")
                            else None
                        ),
                    }
                )

        return {
            "opportunities": sorted(opportunities, key=lambda x: x["score"], reverse=True),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        total = db.count_products()

        return {
            "total_products": total,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rescore/{product_id}")
async def rescore_product(product_id: int):
    """Manually trigger rescoring for a product"""
    try:
        product = db.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        observations = db.get_observations(product_id)
        supplier_data = db.get_supplier_data(product_id)
        score = scorer.score_product(product, observations, supplier_data)

        db.update_product_scores(
            product_id,
            composite_score=score.composite_score,
            velocity_score=score.velocity_score,
            margin_score=score.margin_score,
            saturation_score=score.saturation_score,
        )

        return {"message": "Product rescored", "new_score": score.composite_score}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rescoring product {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
