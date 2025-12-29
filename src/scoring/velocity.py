"""Velocity scoring - measures how fast a product is growing"""

from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..storage.models import ProductObservation

logger = logging.getLogger(__name__)


class VelocityScorer:
    """
    Calculate how fast a product is growing.

    Metrics considered:
    - View count growth rate
    - Sales velocity (if available)
    - Acceleration (is growth speeding up or slowing down)
    - Relative performance vs category baseline

    Output: 0-100 score where:
    - 0-20: Declining or flat
    - 20-40: Slow growth
    - 40-60: Moderate growth
    - 60-80: Strong growth
    - 80-100: Explosive viral growth
    """

    def __init__(self, lookback_hours: int = 72):
        self.lookback_hours = lookback_hours

    def calculate(self, observations: list["ProductObservation"]) -> dict:
        """
        Calculate velocity score from observations.

        Returns:
            {
                "score": 75.5,
                "metrics": {
                    "views_growth_rate": 0.45,
                    "sales_growth_rate": 0.32,
                    "acceleration": 0.12,
                    "hours_of_data": 48
                },
                "signals": ["rapid_growth", "accelerating"]
            }
        """
        if len(observations) < 2:
            return {"score": 0, "metrics": {}, "signals": ["insufficient_data"]}

        # Sort by time
        obs = sorted(observations, key=lambda x: x.observed_at)

        # Filter to lookback window
        cutoff = datetime.utcnow() - timedelta(hours=self.lookback_hours)
        recent = [o for o in obs if o.observed_at >= cutoff]

        if len(recent) < 2:
            recent = obs[-2:]  # Use last 2 if not enough recent

        metrics = {}
        signals = []

        # View growth rate
        views_growth = self._calculate_growth_rate([o.views for o in recent if o.views is not None])
        if views_growth is not None:
            metrics["views_growth_rate"] = round(views_growth, 3)
            if views_growth > 0.5:
                signals.append("rapid_view_growth")

        # Sales growth rate
        sales_growth = self._calculate_growth_rate([o.sales for o in recent if o.sales is not None])
        if sales_growth is not None:
            metrics["sales_growth_rate"] = round(sales_growth, 3)
            if sales_growth > 0.3:
                signals.append("strong_sales_velocity")

        # Acceleration (is growth rate increasing?)
        if len(recent) >= 4:
            acceleration = self._calculate_acceleration(recent)
            metrics["acceleration"] = round(acceleration, 3)
            if acceleration > 0.1:
                signals.append("accelerating")
            elif acceleration < -0.1:
                signals.append("decelerating")

        metrics["hours_of_data"] = round(
            (recent[-1].observed_at - recent[0].observed_at).total_seconds() / 3600, 1
        )

        # Calculate composite velocity score
        score = self._composite_score(metrics)

        return {"score": score, "metrics": metrics, "signals": signals}

    def _calculate_growth_rate(self, values: list[Optional[int]]) -> Optional[float]:
        """Calculate compound growth rate from series"""
        # Filter out None values and ensure we have positive numbers
        values = [v for v in values if v is not None and v > 0]

        if len(values) < 2:
            return None

        # Compound growth rate
        periods = len(values) - 1
        if values[0] == 0:
            return None

        growth = (values[-1] / values[0]) ** (1 / periods) - 1

        return growth

    def _calculate_acceleration(self, observations: list["ProductObservation"]) -> float:
        """Calculate if growth is speeding up or slowing down"""
        # Split into two halves and compare growth rates
        mid = len(observations) // 2
        first_half = observations[:mid]
        second_half = observations[mid:]

        first_growth = self._calculate_growth_rate([o.views for o in first_half if o.views]) or 0
        second_growth = self._calculate_growth_rate([o.views for o in second_half if o.views]) or 0

        return second_growth - first_growth

    def _composite_score(self, metrics: dict) -> float:
        """Combine metrics into 0-100 score"""
        score = 50  # Baseline

        # View growth contribution (0-30 points)
        views_growth = metrics.get("views_growth_rate", 0)
        score += min(30, max(-20, views_growth * 60))

        # Sales growth contribution (0-25 points)
        sales_growth = metrics.get("sales_growth_rate", 0)
        score += min(25, max(-15, sales_growth * 50))

        # Acceleration bonus (0-20 points)
        acceleration = metrics.get("acceleration", 0)
        score += min(20, max(-10, acceleration * 100))

        return max(0, min(100, score))
