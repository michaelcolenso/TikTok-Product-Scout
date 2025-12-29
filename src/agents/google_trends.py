"""Google Trends validation agent."""

from typing import Dict, List

from loguru import logger
from pytrends.request import TrendReq

from ..storage.models import ScrapedProduct
from .base_agent import BaseAgent


class GoogleTrendsAgent(BaseAgent):
    """Uses Google Trends to validate and enrich product signals.

    Purpose:
    - Validate that TikTok trends correlate with search interest
    - Identify geographic hotspots
    - Measure trend velocity over time
    - Compare products to baseline categories

    This is a validation layer, not a primary discovery source.
    """

    @property
    def source_name(self) -> str:
        return "google_trends"

    async def fetch_trending(self, limit: int = 100) -> List[ScrapedProduct]:
        """Not applicable - this agent validates, doesn't discover."""
        raise NotImplementedError("Use get_trend_data() instead")

    async def get_trend_data(
        self, keywords: List[str], timeframe: str = "now 7-d"
    ) -> Dict[str, Dict]:
        """Get trend data for specific keywords.

        Args:
            keywords: List of product names/terms (max 5)
            timeframe: Trends timeframe (now 7-d, today 1-m, etc.)

        Returns:
            Dictionary mapping keywords to trend data
        """
        logger.info(f"Fetching Google Trends data for {len(keywords)} keywords")

        result = {}

        try:
            pytrends = TrendReq(hl="en-US", tz=360)

            # Google Trends accepts max 5 keywords at a time
            keywords_batch = keywords[:5]

            pytrends.build_payload(keywords_batch, timeframe=timeframe)

            # Get interest over time
            interest = pytrends.interest_over_time()

            # Get related queries
            related = pytrends.related_queries()

            # Get geographic breakdown
            geo = pytrends.interest_by_region()

            # Process each keyword
            for kw in keywords_batch:
                if kw in interest.columns:
                    series = interest[kw]

                    result[kw] = {
                        "interest_over_time": series.tolist(),
                        "velocity": self._calculate_velocity(series),
                        "peak_reached": self._detect_peak(series),
                        "current_interest": int(series.iloc[-1]) if len(series) > 0 else 0,
                        "max_interest": int(series.max()) if len(series) > 0 else 0,
                        "geographic_breakdown": (
                            geo[kw].to_dict() if kw in geo.columns else {}
                        ),
                        "related_queries": self._format_related_queries(
                            related.get(kw, {})
                        ),
                    }

        except Exception as e:
            logger.error(f"Error fetching Google Trends data: {e}")

        logger.info(f"Fetched trend data for {len(result)} keywords")
        return result

    def _calculate_velocity(self, series) -> float:
        """Calculate rate of change in interest.

        Args:
            series: Pandas series of interest over time

        Returns:
            Velocity as decimal (0.5 = 50% growth)
        """
        if len(series) < 2:
            return 0.0

        try:
            # Compare last 2 data points to previous 2
            recent = series[-2:].mean()
            previous = series[-4:-2].mean() if len(series) >= 4 else series[0]

            if previous == 0:
                return float("inf") if recent > 0 else 0.0

            return float((recent - previous) / previous)

        except Exception:
            return 0.0

    def _detect_peak(self, series) -> bool:
        """Detect if trend has already peaked.

        Args:
            series: Pandas series of interest over time

        Returns:
            True if trend has peaked
        """
        if len(series) < 3:
            return False

        try:
            # Peak = max was more than 2 periods ago and declining
            max_idx = series.argmax()
            is_peaked = max_idx < len(series) - 2 and series.iloc[-1] < series.iloc[-2]
            return bool(is_peaked)

        except Exception:
            return False

    def _format_related_queries(self, related_data: Dict) -> List[str]:
        """Format related queries for output.

        Args:
            related_data: Related queries data from pytrends

        Returns:
            List of related query strings
        """
        queries = []

        try:
            if "rising" in related_data and related_data["rising"] is not None:
                rising_df = related_data["rising"]
                if not rising_df.empty:
                    queries = rising_df["query"].tolist()[:10]  # Top 10

        except Exception:
            pass

        return queries
