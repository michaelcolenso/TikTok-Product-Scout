"""Saturation scoring - measures market saturation and competition"""

import logging

logger = logging.getLogger(__name__)


class SaturationScorer:
    """
    Measure market saturation / competition level.

    Factors:
    - Number of creators promoting the product
    - Size distribution of creators (all big = saturated)
    - Rate of new creator adoption
    - Time since first viral video

    Output: 0-100 score where:
    - 0-20: Highly saturated, too late
    - 20-40: Competitive, proceed with caution
    - 40-60: Moderate competition
    - 60-80: Early stage, good opportunity
    - 80-100: Very early, first mover advantage

    NOTE: LOWER saturation = HIGHER score (inverse relationship)
    """

    def calculate(
        self, creator_count: int, days_since_first_seen: int, creator_data: list[dict] = None
    ) -> dict:
        """
        Calculate saturation score.

        Returns:
            {
                "score": 65.0,
                "metrics": {
                    "creator_count": 12,
                    "days_active": 5,
                    "adoption_rate": 2.4,
                    "large_creator_ratio": 0.25
                },
                "signals": ["early_stage", "growing_adoption"]
            }
        """
        metrics = {
            "creator_count": creator_count,
            "days_active": days_since_first_seen,
        }

        signals = []

        # Calculate adoption rate (creators per day)
        if days_since_first_seen > 0:
            adoption_rate = creator_count / days_since_first_seen
            metrics["adoption_rate"] = round(adoption_rate, 2)

            if adoption_rate > 10:
                signals.append("viral_adoption")
            elif adoption_rate > 5:
                signals.append("rapid_adoption")
            elif adoption_rate > 2:
                signals.append("growing_adoption")

        # Analyze creator size distribution
        if creator_data:
            large_creators = [c for c in creator_data if c.get("followers", 0) > 100000]
            metrics["large_creator_ratio"] = (
                len(large_creators) / len(creator_data) if creator_data else 0
            )

            if metrics["large_creator_ratio"] > 0.5:
                signals.append("big_creator_dominated")

        # Determine stage
        if creator_count < 5 and days_since_first_seen < 3:
            signals.append("very_early")
        elif creator_count < 20 and days_since_first_seen < 7:
            signals.append("early_stage")
        elif creator_count < 50:
            signals.append("growth_stage")
        else:
            signals.append("saturated")

        score = self._composite_score(metrics)

        return {"score": score, "metrics": metrics, "signals": signals}

    def _composite_score(self, metrics: dict) -> float:
        """
        Calculate saturation score (higher = less saturated = better)
        """
        creator_count = metrics.get("creator_count", 0)
        days_active = metrics.get("days_active", 1)

        # Base score - fewer creators = higher score
        if creator_count <= 5:
            base = 90
        elif creator_count <= 10:
            base = 75
        elif creator_count <= 25:
            base = 60
        elif creator_count <= 50:
            base = 40
        elif creator_count <= 100:
            base = 25
        else:
            base = 10

        # Adjust for time - newer is better
        if days_active <= 2:
            time_bonus = 10
        elif days_active <= 5:
            time_bonus = 5
        elif days_active <= 14:
            time_bonus = 0
        else:
            time_bonus = -10

        # Large creator penalty
        large_ratio = metrics.get("large_creator_ratio", 0)
        large_penalty = large_ratio * 15

        return max(0, min(100, base + time_bonus - large_penalty))
