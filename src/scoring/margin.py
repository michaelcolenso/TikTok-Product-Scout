"""Margin scoring - estimates profit margin potential"""

import logging

logger = logging.getLogger(__name__)


class MarginScorer:
    """
    Estimate profit margin potential.

    Calculation:
    - Compare TikTok selling price to supplier cost
    - Account for shipping, platform fees, ad costs
    - Score based on absolute margin and percentage

    Output: 0-100 score where:
    - 0-20: Negative or razor-thin margins (<10%)
    - 20-40: Low margins (10-25%)
    - 40-60: Moderate margins (25-40%)
    - 60-80: Good margins (40-60%)
    - 80-100: Excellent margins (>60%)
    """

    # Platform fee estimates
    TIKTOK_SHOP_FEE = 0.08  # 8% platform fee
    PAYMENT_PROCESSING = 0.029  # 2.9% + $0.30
    ESTIMATED_AD_COST_PERCENT = 0.15  # 15% of revenue for ads

    def calculate(
        self, selling_price: float, supplier_price: float, shipping_cost: float = 0
    ) -> dict:
        """
        Calculate margin score.

        Returns:
            {
                "score": 72.5,
                "metrics": {
                    "gross_margin_percent": 0.55,
                    "gross_margin_usd": 12.50,
                    "net_margin_percent": 0.32,
                    "net_margin_usd": 7.25,
                    "break_even_cpa": 7.25
                },
                "signals": ["healthy_margin", "room_for_ads"]
            }
        """
        if selling_price <= 0:
            return {"score": 0, "metrics": {}, "signals": ["no_price_data"]}

        total_cost = supplier_price + shipping_cost

        # Gross margin
        gross_margin_usd = selling_price - total_cost
        gross_margin_percent = gross_margin_usd / selling_price

        # Net margin (after fees)
        platform_fees = selling_price * self.TIKTOK_SHOP_FEE
        payment_fees = selling_price * self.PAYMENT_PROCESSING + 0.30
        ad_cost = selling_price * self.ESTIMATED_AD_COST_PERCENT

        net_margin_usd = gross_margin_usd - platform_fees - payment_fees - ad_cost
        net_margin_percent = net_margin_usd / selling_price

        # Break-even CPA (max you can spend on ads per conversion)
        break_even_cpa = gross_margin_usd - platform_fees - payment_fees

        metrics = {
            "gross_margin_percent": round(gross_margin_percent, 3),
            "gross_margin_usd": round(gross_margin_usd, 2),
            "net_margin_percent": round(net_margin_percent, 3),
            "net_margin_usd": round(net_margin_usd, 2),
            "break_even_cpa": round(break_even_cpa, 2),
        }

        signals = []
        if gross_margin_percent >= 0.5:
            signals.append("high_gross_margin")
        if net_margin_percent >= 0.2:
            signals.append("healthy_net_margin")
        if break_even_cpa >= 10:
            signals.append("room_for_ads")
        if net_margin_percent < 0.1:
            signals.append("tight_margins")
        if net_margin_usd < 0:
            signals.append("unprofitable")

        # Calculate score
        score = self._composite_score(metrics)

        return {"score": score, "metrics": metrics, "signals": signals}

    def _composite_score(self, metrics: dict) -> float:
        """Convert margin metrics to 0-100 score"""
        net_margin = metrics.get("net_margin_percent", 0)

        if net_margin < 0:
            return max(0, 20 + net_margin * 100)  # 0-20 for negative margins

        # Scale 0-60% margin to 20-100 score
        score = 20 + min(80, net_margin * 133)

        # Bonus for high absolute margin
        if metrics.get("net_margin_usd", 0) > 15:
            score += 5

        return min(100, score)
