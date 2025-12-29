"""Composite scoring - combines all dimensions into final opportunity score"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TYPE_CHECKING
import logging

from .velocity import VelocityScorer
from .margin import MarginScorer
from .saturation import SaturationScorer

if TYPE_CHECKING:
    from ..storage.models import Product, ProductObservation

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """Final opportunity assessment for a product"""

    composite_score: float
    velocity_score: float
    margin_score: float
    saturation_score: float

    confidence: float  # How much data we have

    signals: list[str]
    recommendation: str  # "strong_buy", "buy", "watch", "pass", "too_late"

    details: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class CompositeScorer:
    """
    Combines all scoring dimensions into final opportunity score.

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

    WEIGHTS = {"velocity": 0.35, "margin": 0.30, "saturation": 0.35}

    def __init__(self):
        self.velocity_scorer = VelocityScorer()
        self.margin_scorer = MarginScorer()
        self.saturation_scorer = SaturationScorer()

    def score_product(
        self,
        product: "Product",
        observations: list["ProductObservation"],
        supplier_data: dict = None,
    ) -> OpportunityScore:
        """
        Calculate comprehensive opportunity score for a product.
        """
        all_signals = []

        # Velocity scoring
        velocity_result = self.velocity_scorer.calculate(observations)
        velocity_score = velocity_result["score"]
        all_signals.extend(velocity_result.get("signals", []))

        # Margin scoring
        if supplier_data:
            selling_price = self._get_latest_price(observations)
            margin_result = self.margin_scorer.calculate(
                selling_price=selling_price,
                supplier_price=supplier_data.get("min_price", 0),
                shipping_cost=supplier_data.get("shipping_estimate", 0),
            )
            margin_score = margin_result["score"]
            all_signals.extend(margin_result.get("signals", []))
        else:
            margin_score = 50  # Neutral if no supplier data
            margin_result = {"metrics": {}}
            all_signals.append("no_supplier_data")

        # Saturation scoring
        creator_count = self._estimate_creator_count(observations)
        days_active = (datetime.utcnow() - product.first_seen_at).days
        saturation_result = self.saturation_scorer.calculate(
            creator_count=creator_count, days_since_first_seen=max(1, days_active)
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
            confidence=confidence,
            signals=all_signals,
            recommendation=recommendation,
            details={
                "velocity": velocity_result.get("metrics", {}),
                "margin": margin_result.get("metrics", {}),
                "saturation": saturation_result.get("metrics", {}),
            },
        )

    def _classify(self, score: float, signals: list) -> str:
        """Classify the opportunity"""
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
        self, observations: list["ProductObservation"], supplier_data: dict
    ) -> float:
        """Estimate confidence based on data availability"""
        confidence = 0.5  # Base

        # More observations = higher confidence
        confidence += min(0.2, len(observations) * 0.02)

        # Multiple sources = higher confidence
        sources = set(o.source for o in observations)
        confidence += min(0.15, len(sources) * 0.05)

        # Supplier data = higher confidence
        if supplier_data:
            confidence += 0.15

        return min(1.0, confidence)

    def _get_latest_price(self, observations: list["ProductObservation"]) -> float:
        """Get most recent price from observations"""
        priced = [o for o in observations if o.price_usd]
        if not priced:
            return 0
        return max(priced, key=lambda x: x.observed_at).price_usd

    def _estimate_creator_count(self, observations: list["ProductObservation"]) -> int:
        """Estimate creator count from observations"""
        # For MVP, use a simple heuristic based on view diversity
        # In production, this would come from CreatorTracking table

        if not observations:
            return 0

        # Estimate: more observations from different sources suggests more creators
        sources = set(o.source for o in observations)
        obs_count = len(observations)

        # Simple heuristic
        estimated = min(100, obs_count * 2 + len(sources) * 3)

        return estimated
