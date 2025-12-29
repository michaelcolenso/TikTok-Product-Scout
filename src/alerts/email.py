"""Email alerting system."""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from loguru import logger

from ..scoring.composite import OpportunityScore
from ..storage.models import Product


class EmailAlerter:
    """Send product alerts via email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        recipients: List[str],
    ):
        """Initialize email alerter.

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            recipients: List of recipient email addresses
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.recipients = recipients

    async def send_alert(self, product: Product, score: OpportunityScore) -> bool:
        """Send email alert for product.

        Args:
            product: Product instance
            score: Opportunity score

        Returns:
            True if email sent successfully
        """
        if not self.recipients:
            logger.warning("No email recipients configured")
            return False

        try:
            subject = self._create_subject(product, score)
            html_body = self._create_html_body(product, score)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = ", ".join(self.recipients)

            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent for product: {product.canonical_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _create_subject(self, product: Product, score: OpportunityScore) -> str:
        """Create email subject line.

        Args:
            product: Product instance
            score: Opportunity score

        Returns:
            Email subject string
        """
        emoji_map = {
            "strong_buy": "🔥🔥🔥",
            "buy": "🔥",
            "watch": "👀",
            "pass": "⚠️",
            "too_late": "❌",
        }

        emoji = emoji_map.get(score.recommendation, "")
        return f"{emoji} TikTok Product Scout: {score.recommendation.upper().replace('_', ' ')} - {product.canonical_name}"

    def _create_html_body(self, product: Product, score: OpportunityScore) -> str:
        """Create HTML email body.

        Args:
            product: Product instance
            score: Opportunity score

        Returns:
            HTML string
        """
        # Color based on recommendation
        color_map = {
            "strong_buy": "#00FF00",
            "buy": "#90EE90",
            "watch": "#FFFF00",
            "pass": "#FFA500",
            "too_late": "#FF0000",
        }

        color = color_map.get(score.recommendation, "#808080")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: #000; padding: 20px; border-radius: 5px; }}
                .score-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }}
                .score-box {{ background-color: #f4f4f4; padding: 15px; border-radius: 5px; }}
                .score-label {{ font-size: 12px; color: #666; }}
                .score-value {{ font-size: 24px; font-weight: bold; color: #333; }}
                .details {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{score.recommendation.upper().replace('_', ' ')}</h1>
                    <h2>{product.canonical_name}</h2>
                </div>

                <div class="score-grid">
                    <div class="score-box">
                        <div class="score-label">Composite Score</div>
                        <div class="score-value">{score.composite_score}/100</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Confidence</div>
                        <div class="score-value">{score.confidence * 100:.0f}%</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Velocity</div>
                        <div class="score-value">{score.velocity_score}/100</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Margin</div>
                        <div class="score-value">{score.margin_score}/100</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Saturation</div>
                        <div class="score-value">{score.saturation_score}/100</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Category</div>
                        <div class="score-value" style="font-size: 16px;">{product.category or 'Unknown'}</div>
                    </div>
                </div>

                <div class="details">
                    <h3>📌 Signals</h3>
                    <p>{', '.join(score.signals) if score.signals else 'None'}</p>
                </div>
        """

        # Add margin details
        if score.details.get("margin"):
            margin = score.details["margin"]
            if margin.get("net_margin_percent") is not None:
                html += f"""
                <div class="details">
                    <h3>💵 Margin Analysis</h3>
                    <ul>
                        <li><strong>Gross Margin:</strong> {margin.get('gross_margin_percent', 0)*100:.1f}% (${margin.get('gross_margin_usd', 0):.2f})</li>
                        <li><strong>Net Margin:</strong> {margin.get('net_margin_percent', 0)*100:.1f}% (${margin.get('net_margin_usd', 0):.2f})</li>
                        <li><strong>Break-even CPA:</strong> ${margin.get('break_even_cpa', 0):.2f}</li>
                    </ul>
                </div>
                """

        html += f"""
                <div class="footer">
                    <p>First seen: {product.first_seen_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                    <p>TikTok Product Scout | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html
