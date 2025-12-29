"""Discord alerting system."""

from datetime import datetime
from typing import Optional

import httpx
from loguru import logger

from ..scoring.composite import OpportunityScore
from ..storage.models import Product


class DiscordAlerter:
    """Send product alerts to Discord via webhook."""

    def __init__(self, webhook_url: str):
        """Initialize Discord alerter.

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url

    async def send_alert(self, product: Product, score: OpportunityScore) -> bool:
        """Send a rich embed alert to Discord.

        Args:
            product: Product instance
            score: Opportunity score

        Returns:
            True if alert sent successfully
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        try:
            embed = self._create_embed(product, score)
            payload = {"embeds": [embed]}

            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10)
                response.raise_for_status()

            logger.info(f"Discord alert sent for product: {product.canonical_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False

    def _create_embed(self, product: Product, score: OpportunityScore) -> dict:
        """Create Discord embed for product alert.

        Args:
            product: Product instance
            score: Opportunity score

        Returns:
            Discord embed dictionary
        """
        # Color based on recommendation
        colors = {
            "strong_buy": 0x00FF00,  # Green
            "buy": 0x90EE90,  # Light green
            "watch": 0xFFFF00,  # Yellow
            "pass": 0xFFA500,  # Orange
            "too_late": 0xFF0000,  # Red
        }

        color = colors.get(score.recommendation, 0x808080)

        # Create title with emoji
        emoji_map = {
            "strong_buy": "🔥🔥🔥",
            "buy": "🔥",
            "watch": "👀",
            "pass": "⚠️",
            "too_late": "❌",
        }

        emoji = emoji_map.get(score.recommendation, "")
        title = f"{emoji} {score.recommendation.upper().replace('_', ' ')}: {product.canonical_name}"

        # Build fields
        fields = [
            {
                "name": "📊 Composite Score",
                "value": f"**{score.composite_score}/100**",
                "inline": True,
            },
            {
                "name": "🚀 Velocity",
                "value": f"{score.velocity_score}/100",
                "inline": True,
            },
            {
                "name": "💰 Margin",
                "value": f"{score.margin_score}/100",
                "inline": True,
            },
            {
                "name": "📈 Saturation",
                "value": f"{score.saturation_score}/100",
                "inline": True,
            },
            {
                "name": "✅ Confidence",
                "value": f"{score.confidence * 100:.0f}%",
                "inline": True,
            },
            {
                "name": "🏷️ Category",
                "value": product.category or "Unknown",
                "inline": True,
            },
        ]

        # Add signals if available
        if score.signals:
            signals_text = ", ".join(score.signals[:5])
            fields.append({
                "name": "📌 Signals",
                "value": signals_text,
                "inline": False,
            })

        # Add margin details if available
        if score.details.get("margin"):
            margin = score.details["margin"]
            if margin.get("net_margin_percent") is not None:
                margin_text = (
                    f"**Gross:** {margin.get('gross_margin_percent', 0)*100:.1f}% "
                    f"(${margin.get('gross_margin_usd', 0):.2f})\n"
                    f"**Net:** {margin.get('net_margin_percent', 0)*100:.1f}% "
                    f"(${margin.get('net_margin_usd', 0):.2f})\n"
                    f"**Break-even CPA:** ${margin.get('break_even_cpa', 0):.2f}"
                )
                fields.append({
                    "name": "💵 Margin Analysis",
                    "value": margin_text,
                    "inline": False,
                })

        # Add velocity details if available
        if score.details.get("velocity"):
            velocity = score.details["velocity"]
            if velocity.get("views_growth_rate") is not None:
                velocity_text = (
                    f"**View Growth:** {velocity.get('views_growth_rate', 0)*100:.1f}%\n"
                )
                if velocity.get("sales_growth_rate") is not None:
                    velocity_text += (
                        f"**Sales Growth:** {velocity.get('sales_growth_rate', 0)*100:.1f}%\n"
                    )
                if velocity.get("acceleration") is not None:
                    velocity_text += (
                        f"**Acceleration:** {velocity.get('acceleration', 0)*100:.1f}%"
                    )
                fields.append({
                    "name": "📈 Velocity Details",
                    "value": velocity_text,
                    "inline": False,
                })

        embed = {
            "title": title,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"First seen: {product.first_seen_at.strftime('%Y-%m-%d %H:%M UTC')} | TikTok Product Scout"
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return embed
