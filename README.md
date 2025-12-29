# TikTok Product Scout

**Agentic Viral Product Discovery System**

TikTok Product Scout is an automated tool that identifies trending products on TikTok before they reach market saturation. The system aggregates signals from multiple data sources, calculates opportunity scores, and delivers actionable alerts to dropshippers, TikTok affiliates, and e-commerce operators.

## Core Value Proposition

Catch products in the 24-72 hour window after trend emergence but before creator saturation.

## Features

- **Multi-Source Data Collection**: Scrapes TikTok Creative Center, AliExpress, and other sources
- **Intelligent Scoring**: Combines velocity, margin, and saturation metrics
- **Real-time Alerts**: Discord notifications for high-opportunity products
- **REST API**: Query products and opportunities programmatically
- **Automated Scheduling**: Continuous monitoring with configurable intervals

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- Discord webhook URL (for alerts)

### Installation

#### Option 1: Local Setup

\`\`\`bash
# Clone the repository
git clone <your-repo-url>
cd TikTok-Product-Scout

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Configure environment variables
cp .env.example .env
# Edit .env and add your Discord webhook URL

# Activate virtual environment
source venv/bin/activate
\`\`\`

#### Option 2: Docker Setup

\`\`\`bash
# Clone the repository
git clone <your-repo-url>
cd TikTok-Product-Scout

# Configure environment variables
cp .env.example .env
# Edit .env and add your Discord webhook URL

# Build and run with Docker Compose
docker-compose up -d
\`\`\`

### Running the System

The system has three modes of operation:

#### 1. Single Scrape (Testing)

Run a one-time scrape to test the system:

\`\`\`bash
python -m src.main scrape
\`\`\`

#### 2. Scheduler Mode (Continuous)

Run continuous automated scraping and alerting:

\`\`\`bash
python -m src.main scheduler
\`\`\`

This will:
- Scrape TikTok Creative Center every 4 hours
- Match supplier prices every 12 hours
- Score products every 2 hours
- Check for alerts every 30 minutes

#### 3. API Server

Run the REST API server:

\`\`\`bash
python -m src.main api
\`\`\`

The API will be available at \`http://localhost:8000\`

API Documentation: \`http://localhost:8000/docs\`

## Configuration

Edit \`config/config.yaml\` to customize scraping intervals, alert thresholds, and scoring weights.

### Anti-Bot Evasion & Proxy Setup

**IMPORTANT**: TikTok and AliExpress have sophisticated anti-bot defenses. For production use, proper stealth configuration and proxies are essential.

#### Stealth Mode (Built-in)

The system includes comprehensive stealth features enabled by default:

- ✅ **Fingerprint Randomization**: Randomizes user-agents, viewports, timezones, and browser fingerprints
- ✅ **Human-Like Behavior**: Natural mouse movements, realistic scrolling patterns, variable delays
- ✅ **Automation Hiding**: Patches `navigator.webdriver` and other automation indicators
- ✅ **Resource Blocking**: Blocks unnecessary images/fonts/ads to reduce fingerprint surface
- ✅ **Block Detection**: Automatically detects CAPTCHAs and IP blocks with retry logic

Configure in `config/config.yaml`:

\`\`\`yaml
scraping:
  stealth:
    enabled: true        # Enable stealth mode (highly recommended)
    headless: true       # Set to false for debugging
    block_images: true   # Block images for speed (set false if needed)
\`\`\`

#### Proxy Configuration (Required for Production)

**Why Proxies Are Essential:**
- TikTok blocks datacenter IPs and single-IP scrapers within hours
- Residential/mobile proxies are required for sustained scraping
- Proxy rotation prevents rate limiting and bans

**Recommended Proxy Providers:**
- **BrightData** - Premium residential proxies (best for TikTok)
- **Oxylabs** - High-quality, reliable for e-commerce
- **Smartproxy** - Good value, solid performance
- **NetNut** - Fast residential proxies

**Setup Steps:**

1. **Get proxies** from a provider (use residential or mobile, NOT datacenter)

2. **Configure in `config/config.yaml`**:

\`\`\`yaml
scraping:
  proxies:
    enabled: true
    sticky_minutes: 15  # Keep same IP for 15 min before rotating
    urls:
      - "http://user:pass@proxy1.example.com:8080"
      - "http://user:pass@proxy2.example.com:8080"
      - "http://user:pass@proxy3.example.com:8080"
\`\`\`

3. **See `config/proxy.example.yaml` for detailed examples** including:
   - BrightData configuration
   - Smartproxy setup
   - SOCKS5 proxies
   - Session-based proxies
   - Security best practices

**Testing Your Proxies:**

\`\`\`bash
# Test proxy connectivity
curl -x http://user:pass@proxy.example.com:8080 https://ipinfo.io

# Verify residential IP (should show ISP, not "hosting")
curl -x http://user:pass@proxy.example.com:8080 https://whoer.net
\`\`\`

**Cost Optimization Tips:**
- Start with 2-3 proxies and scale as needed
- Enable `block_images: true` to reduce bandwidth costs
- Use sticky sessions (15-30 min) to minimize IP changes
- Monitor logs for failed proxies

**Without Proxies:**
The system will work for testing/development, but expect blocks within a few runs on TikTok. For continuous production use, proxies are **mandatory**.

## API Endpoints

- \`GET /products\` - List products with filtering
- \`GET /products/{id}\` - Get product details
- \`GET /opportunities\` - Get top opportunities
- \`GET /stats\` - System statistics
- \`POST /rescore/{id}\` - Manually rescore a product

## Scoring System

Products are scored on three dimensions:

### Velocity Score (0-100)
Measures growth rate - how fast the product is trending.

### Margin Score (0-100)
Estimates profit potential based on selling price vs supplier cost.

### Saturation Score (0-100)
Measures market timing - fewer creators = higher score.

### Composite Score
Final score = (Velocity × 0.35) + (Margin × 0.30) + (Saturation × 0.35)

**Recommendations:**
- 80-100: **Strong Buy** - Act now
- 65-79: **Buy** - Good opportunity
- 50-64: **Watch** - Monitor closely
- 35-49: **Pass** - Not ideal timing
- 0-34: **Too Late** - Already saturated

## Discord Alerts

Set up Discord webhook in .env:

\`\`\`bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
\`\`\`

## License

MIT License - see LICENSE file for details

## Disclaimer

This tool is for educational and research purposes. Please respect rate limits and terms of service.

**Built with:** Python, FastAPI, Playwright, SQLAlchemy, APScheduler
