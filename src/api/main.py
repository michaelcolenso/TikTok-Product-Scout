"""FastAPI application for TikTok Product Scout."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ..scoring.composite import CompositeScorer
from ..storage.database import Database
from ..utils.config import get_config

# Initialize FastAPI app
app = FastAPI(
    title="TikTok Product Scout API",
    description="API for viral product discovery and scoring",
    version="1.0.0",
)

# Load configuration
config = get_config()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database and scorer
db = Database(config.database.url)
scorer = CompositeScorer(config.model_dump())


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("TikTok Product Scout API starting up")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("TikTok Product Scout API shutting down")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "TikTok Product Scout API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/products")
async def list_products(
    min_score: float = Query(0, ge=0, le=100, description="Minimum composite score"),
    category: Optional[str] = Query(None, description="Filter by category"),
    recommendation: Optional[str] = Query(
        None, description="Filter by recommendation (strong_buy, buy, watch, pass, too_late)"
    ),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List products with optional filtering.

    Args:
        min_score: Minimum composite score (0-100)
        category: Filter by product category
        recommendation: Filter by recommendation type
        limit: Number of results (max 200)
        offset: Pagination offset

    Returns:
        List of products with scores
    """
    try:
        products = db.query_products(
            min_score=min_score,
            category=category,
            limit=limit,
            offset=offset,
        )

        results = []
        for product in products:
            # Filter by recommendation if specified
            if recommendation:
                if product.composite_score >= 80 and recommendation != "strong_buy":
                    continue
                elif 65 <= product.composite_score < 80 and recommendation != "buy":
                    continue
                elif 50 <= product.composite_score < 65 and recommendation != "watch":
                    continue
                elif 35 <= product.composite_score < 50 and recommendation != "pass":
                    continue
                elif product.composite_score < 35 and recommendation != "too_late":
                    continue

            results.append({
                "id": product.id,
                "name": product.canonical_name,
                "category": product.category,
                "composite_score": product.composite_score,
                "velocity_score": product.velocity_score,
                "margin_score": product.margin_score,
                "saturation_score": product.saturation_score,
                "first_seen": product.first_seen_at.isoformat(),
                "last_updated": product.last_updated_at.isoformat(),
            })

        return {
            "products": results,
            "total": len(results),
            "offset": offset,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    """Get detailed product information including full scoring breakdown.

    Args:
        product_id: Product ID

    Returns:
        Detailed product information
    """
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
                "last_updated": product.last_updated_at.isoformat(),
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
                    "orders": o.orders,
                    "reviews": o.reviews,
                    "rating": o.rating,
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
    """Get top opportunities ranked by composite score.

    Only returns products with actionable recommendations.

    Args:
        min_score: Minimum composite score
        limit: Maximum number of results

    Returns:
        List of top opportunities
    """
    try:
        products = db.query_products(min_score=min_score, limit=limit)

        opportunities = []
        for product in products:
            observations = db.get_observations(product.id)
            supplier_data = db.get_supplier_data(product.id)
            score = scorer.score_product(product, observations, supplier_data)

            if score.recommendation in ["strong_buy", "buy", "watch"]:
                opportunities.append({
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
                    "velocity": score.velocity_score,
                    "saturation": score.saturation_score,
                })

        # Sort by score descending
        opportunities.sort(key=lambda x: x["score"], reverse=True)

        return {
            "opportunities": opportunities,
            "count": len(opportunities),
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get system statistics.

    Returns:
        System statistics and metrics
    """
    try:
        return {
            "total_products": db.count_products(),
            "products_by_recommendation": db.count_by_recommendation(),
            "products_by_category": db.count_by_category(),
            "observations_today": db.count_observations_today(),
            "alerts_sent_today": db.count_alerts_today(),
            "last_scrape": (
                db.get_last_scrape_time().isoformat()
                if db.get_last_scrape_time()
                else None
            ),
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rescore/{product_id}")
async def rescore_product(product_id: int):
    """Manually trigger rescoring for a product.

    Args:
        product_id: Product ID

    Returns:
        Updated score information
    """
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

        return {
            "message": "Product rescored successfully",
            "product_id": product_id,
            "new_score": score.composite_score,
            "recommendation": score.recommendation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rescoring product {product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=False,
    )
