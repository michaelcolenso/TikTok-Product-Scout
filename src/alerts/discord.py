"""Discord webhook alerter"""

import httpx
from datetime import datetime
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..storage.models import Product
    from ..scoring.composite import OpportunityScore

logger = logging.getLogger(__name__)


class DiscordAlerter:
    """Send product alerts to Discord via webhook"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_alert(self, product: "Product", score: "OpportunityScore"):
        """
        Send a rich embed alert to Discord.
        """
        # Color based on recommendation
        colors = {
            "strong_buy": 0x00FF00,  # Green
            "buy": 0x90EE90,  # Light green
            "watch": 0xFFFF00,  # Yellow
            "pass": 0xFFA500,  # Orange
            "too_late": 0xFF0000,  # Red
        }

        embed = {
            "title": f"🔥 {score.recommendation.upper().replace('_', ' ')}: {product.canonical_name}",
            "color": colors.get(score.recommendation, 0x808080),
            "fields": [
                {
                    "name": "Composite Score",
                    "value": f"**{score.composite_score}/100**",
                    "inline": True,
                },
                {"name": "Velocity", "value": f"{score.velocity_score}/100", "inline": True},
                {"name": "Margin", "value": f"{score.margin_score}/100", "inline": True},
                {"name": "Saturation", "value": f"{score.saturation_score}/100", "inline": True},
                {
                    "name": "Confidence",
                    "value": f"{score.confidence * 100:.0f}%",
                    "inline": True,
                },
                {
                    "name": "Category",
                    "value": product.category or "Unknown",
                    "inline": True,
                },
                {
                    "name": "Signals",
                    "value": ", ".join(score.signals[:5]) or "None",
                    "inline": False,
                },
            ],
            "footer": {
                "text": f"First seen: {product.first_seen_at.strftime('%Y-%m-%d %H:%M UTC')}"
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add margin details if available
        if score.details.get("margin") and score.details["margin"]:
            margin = score.details["margin"]
            embed["fields"].append(
                {
                    "name": "💰 Margin Analysis",
                    "value": (
                        f"Gross: {margin.get('gross_margin_percent', 0)*100:.1f}% (${margin.get('gross_margin_usd', 0):.2f})\n"
                        f"Net: {margin.get('net_margin_percent', 0)*100:.1f}% (${margin.get('net_margin_usd', 0):.2f})\n"
                        f"Break-even CPA: ${margin.get('break_even_cpa', 0):.2f}"
                    ),
                    "inline": False,
                }
            )

        payload = {"embeds": [embed]}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)
                response.raise_for_status()
                logger.info(f"Discord alert sent for product: {product.canonical_name}")
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            raise
