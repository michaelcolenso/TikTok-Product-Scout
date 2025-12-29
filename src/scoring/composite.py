"""Composite scoring engine that combines all scoring dimensions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

from ..storage.models import Product, ProductObservation
from .margin import MarginScorer
from .saturation import SaturationScorer
from .velocity import VelocityScorer


@dataclass
class OpportunityScore:
    """Final opportunity assessment for a product."""

    composite_score: float
    velocity_score: float
    margin_score: float
    saturation_score: float

    confidence: float  # How much data we have

    signals: List[str]
    recommendation: str  # "strong_buy", "buy", "watch", "pass", "too_late"

    details: Dict


class CompositeScorer:
    """Combines all scoring dimensions into final opportunity score.

    Weighting:
    - Velocity: 35% (growth is king)
    - Margin: 30% (need to make money)
    - Saturation: 35% (timing is everything)

    Final classification:
    - 80-100: Strong Buy - Act now
    - 65-79: Buy - Good opportunity
    - 50-64: Watch - Monitor closely
    - 35-49: Pass - Not ideal timing
    - 0-34: Too Late - Already saturated
    """

    WEIGHTS = {
        "velocity": 0.35,
        "margin": 0.30,
        "saturation": 0.35,
    }

    def __init__(self, config: Optional[Dict] = None):
        """Initialize composite scorer.

        Args:
            config: Optional configuration dictionary
        """
        if config:
            scoring_config = config.get("scoring", {})
            self.WEIGHTS = scoring_config.get("weights", self.WEIGHTS)

            self.velocity_scorer = VelocityScorer()
            self.margin_scorer = MarginScorer(scoring_config)
            self.saturation_scorer = SaturationScorer(scoring_config)
        else:
            self.velocity_scorer = VelocityScorer()
            self.margin_scorer = MarginScorer()
            self.saturation_scorer = SaturationScorer()

    def score_product(
        self,
        product: Product,
        observations: List[ProductObservation],
        supplier_data: Optional[Dict] = None,
    ) -> OpportunityScore:
        """Calculate comprehensive opportunity score for a product.

        Args:
            product: Product instance
            observations: List of product observations
            supplier_data: Optional supplier pricing data

        Returns:
            OpportunityScore instance
        """
        all_signals = []

        # Velocity scoring
        velocity_result = self.velocity_scorer.calculate(observations)
        velocity_score = velocity_result["score"]
        all_signals.extend(velocity_result.get("signals", []))

        # Margin scoring
        if supplier_data and supplier_data.get("min_price"):
            selling_price = self._get_latest_price(observations)
            if selling_price > 0:
                margin_result = self.margin_scorer.calculate(
                    selling_price=selling_price,
                    supplier_price=supplier_data.get("min_price", 0),
                    shipping_cost=supplier_data.get("shipping_estimate", 0),
                )
                margin_score = margin_result["score"]
                all_signals.extend(margin_result.get("signals", []))
            else:
                margin_score = 50.0  # Neutral if no price data
                margin_result = {"metrics": {}, "signals": ["no_price_data"]}
                all_signals.append("no_price_data")
        else:
            margin_score = 50.0  # Neutral if no supplier data
            margin_result = {"metrics": {}, "signals": ["no_supplier_data"]}
            all_signals.append("no_supplier_data")

        # Saturation scoring
        creator_count = self._estimate_creator_count(observations)
        days_active = (datetime.utcnow() - product.first_seen_at).days
        saturation_result = self.saturation_scorer.calculate(
            creator_count=creator_count,
            days_since_first_seen=max(1, days_active),  # Minimum 1 day
        )
        saturation_score = saturation_result["score"]
        all_signals.extend(saturation_result.get("signals", []))

        # Composite score
        composite = (
            velocity_score * self.WEIGHTS["velocity"]
            + margin_score * self.WEIGHTS["margin"]
            + saturation_score * self.WEIGHTS["saturation"]
        )

        # Confidence based on data quality
        confidence = self._calculate_confidence(observations, supplier_data)

        # Classification
        recommendation = self._classify(composite, all_signals)

        return OpportunityScore(
            composite_score=round(composite, 1),
            velocity_score=round(velocity_score, 1),
            margin_score=round(margin_score, 1),
            saturation_score=round(saturation_score, 1),
            confidence=round(confidence, 2),
            signals=all_signals,
            recommendation=recommendation,
            details={
                "velocity": velocity_result.get("metrics", {}),
                "margin": margin_result.get("metrics", {}),
                "saturation": saturation_result.get("metrics", {}),
            },
        )

    def _classify(self, score: float, signals: List[str]) -> str:
        """Classify the opportunity based on score and signals.

        Args:
            score: Composite score
            signals: List of signals from all scorers

        Returns:
            Recommendation string
        """
        # Override based on critical signals
        if "unprofitable" in signals:
            return "pass"
        if "saturated" in signals and score < 60:
            return "too_late"

        if score >= 80:
            return "strong_buy"
        elif score >= 65:
            return "buy"
        elif score >= 50:
            return "watch"
        elif score >= 35:
            return "pass"
        else:
            return "too_late"

    def _calculate_confidence(
        self, observations: List[ProductObservation], supplier_data: Optional[Dict]
    ) -> float:
        """Estimate confidence based on data availability.

        Args:
            observations: List of observations
            supplier_data: Supplier data dictionary

        Returns:
            Confidence score from 0-1
        """
        confidence = 0.5  # Base

        # More observations = higher confidence
        confidence += min(0.2, len(observations) * 0.02)

        # Multiple sources = higher confidence
        sources = set(o.source for o in observations)
        confidence += min(0.15, len(sources) * 0.05)

        # Supplier data = higher confidence
        if supplier_data and supplier_data.get("min_price"):
            confidence += 0.15

        return min(1.0, confidence)

    def _get_latest_price(self, observations: List[ProductObservation]) -> float:
        """Get most recent price from observations.

        Args:
            observations: List of observations

        Returns:
            Latest price or 0 if no price found
        """
        priced = [o for o in observations if o.price_usd is not None and o.price_usd > 0]
        if not priced:
            return 0.0

        latest = max(priced, key=lambda x: x.observed_at)
        return latest.price_usd

    def _estimate_creator_count(self, observations: List[ProductObservation]) -> int:
        """Estimate creator count from observations.

        This is a placeholder - in production, this would query the CreatorTracking table.

        Args:
            observations: List of observations

        Returns:
            Estimated creator count
        """
        # Rough estimate based on view diversity and data sources
        # In production, query CreatorTracking table
        view_counts = [o.views for o in observations if o.views is not None]

        if not view_counts:
            return 5  # Default estimate

        # Simple heuristic: more observations with high variance = more creators
        if len(view_counts) > 5:
            import numpy as np

            variance = np.var(view_counts)
            mean = np.mean(view_counts)

            if mean > 0:
                cv = variance / mean  # Coefficient of variation
                # High variance relative to mean suggests multiple creators
                return min(100, int(5 + cv * 10))

        return len(observations)  # Rough estimate
