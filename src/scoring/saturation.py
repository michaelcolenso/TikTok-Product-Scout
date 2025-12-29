"""Saturation scoring engine for measuring market competition."""

from typing import Dict, List, Optional

from loguru import logger


class SaturationScorer:
    """Measure market saturation / competition level.

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

    def __init__(self, config: Optional[Dict] = None):
        """Initialize saturation scorer.

        Args:
            config: Optional configuration dictionary
        """
        self.large_creator_followers = 100000
        self.early_stage_creators = 5
        self.early_stage_days = 3

        if config:
            saturation_config = config.get("saturation", {})
            self.large_creator_followers = saturation_config.get(
                "large_creator_followers", 100000
            )
            self.early_stage_creators = saturation_config.get("early_stage_creators", 5)
            self.early_stage_days = saturation_config.get("early_stage_days", 3)

    def calculate(
        self,
        creator_count: int,
        days_since_first_seen: int,
        creator_data: Optional[List[Dict]] = None,
    ) -> Dict:
        """Calculate saturation score.

        Args:
            creator_count: Number of creators promoting product
            days_since_first_seen: Days since product first appeared
            creator_data: Optional detailed creator information

        Returns:
            Dictionary with score, metrics, and signals
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
            else:
                signals.append("slow_adoption")

        # Analyze creator size distribution
        if creator_data:
            large_creators = [
                c for c in creator_data
                if c.get("followers", 0) > self.large_creator_followers
            ]
            large_creator_ratio = len(large_creators) / len(creator_data) if creator_data else 0
            metrics["large_creator_ratio"] = round(large_creator_ratio, 2)
            metrics["large_creator_count"] = len(large_creators)

            if large_creator_ratio > 0.5:
                signals.append("big_creator_dominated")

        # Determine stage
        if creator_count < self.early_stage_creators and days_since_first_seen < self.early_stage_days:
            signals.append("very_early")
        elif creator_count < 20 and days_since_first_seen < 7:
            signals.append("early_stage")
        elif creator_count < 50:
            signals.append("growth_stage")
        else:
            signals.append("saturated")

        # Calculate score
        score = self._composite_score(metrics)

        return {
            "score": round(score, 1),
            "metrics": metrics,
            "signals": signals,
        }

    def _composite_score(self, metrics: Dict) -> float:
        """Calculate saturation score (higher = less saturated = better).

        Args:
            metrics: Dictionary of saturation metrics

        Returns:
            Score from 0-100
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
