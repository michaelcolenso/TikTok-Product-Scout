# 🔥 TikTok Product Scout

An agentic automation tool that identifies trending products on TikTok before they reach market saturation. Catch products in the 24-72 hour window after trend emergence but before creator saturation.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🎯 Core Value Proposition

Discover viral products at the perfect moment:
- **Early Detection**: Identify trends within 24-72 hours of emergence
- **Multi-Source Intelligence**: Aggregate signals from TikTok, Amazon, AliExpress, and Google
- **Smart Scoring**: AI-driven opportunity scoring based on velocity, margin, and saturation
- **Automated Alerts**: Real-time notifications via Discord/Email for high-potential products

## ⭐ Key Features

### 📊 Multi-Platform Data Collection
- **TikTok Creative Center**: Trending products, view counts, engagement metrics
- **TikTok Shop**: Sales velocity, pricing, reviews
- **AliExpress**: Supplier pricing for margin calculation
- **Amazon Movers & Shakers**: Cross-platform validation
- **Google Trends**: Search interest validation

### 🤖 Intelligent Scoring Engine
- **Velocity Score** (35%): Measures growth rate and acceleration
- **Margin Score** (30%): Estimates profit potential after fees
- **Saturation Score** (35%): Evaluates competition and timing
- **Composite Score**: Final 0-100 opportunity rating

### 🔔 Automated Alerting
- Discord webhook integration
- Email notifications
- Configurable thresholds
- Rich embeds with full analysis

### 🚀 Production Ready
- RESTful API with FastAPI
- Scheduled scraping with APScheduler
- Docker containerization
- Anti-detection features
- Comprehensive logging

## 📋 Requirements

- Python 3.11+
- SQLite (included)
- Playwright (for browser automation)
- Optional: Docker & Docker Compose

## 🚀 Quick Start

### Option 1: Local Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/tiktok-product-scout.git
cd tiktok-product-scout

# Run setup script
python scripts/setup.py

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Run the scheduler
python -m src scheduler

# Or run the API server (in a separate terminal)
python -m src api
```

### Option 2: Docker Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/tiktok-product-scout.git
cd tiktok-product-scout

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following:

```env
# Database
DATABASE_URL=sqlite:///data/db/products.db

# Discord Alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-webhook-url

# Email Alerts (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_RECIPIENTS=alerts@yourcompany.com

# Third-party APIs (optional)
KALODATA_API_KEY=your-key
FASTMOSS_API_KEY=your-key

# Logging
LOG_LEVEL=INFO
```

### Configuration File

Edit `config/config.yaml` to customize:
- Scraping schedules
- Scoring weights
- Alert thresholds
- Agent settings

## 📚 Usage

### Running Components

```bash
# Run the scheduler (scraping + scoring + alerts)
python -m src scheduler

# Run the API server
python -m src api

# Run a single agent manually
python -m src agent tiktok_creative_center

# Run scoring manually
python -m src score

# Check for alerts manually
python -m src alerts
```

### API Endpoints

The API server runs on `http://localhost:8000` by default.

#### List Products
```bash
GET /products?min_score=70&limit=20
```

#### Get Product Details
```bash
GET /products/{product_id}
```

#### Get Top Opportunities
```bash
GET /opportunities?min_score=65&limit=10
```

#### Get Statistics
```bash
GET /stats
```

#### Rescore Product
```bash
POST /rescore/{product_id}
```

### API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TikTok Product Scout                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │   Scrapers   │───▶│  Data Lake   │───▶│   Scoring    │───▶│   Alerts   │ │
│  │   (Agents)   │    │  (Storage)   │    │   Engine     │    │  & Output  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

- **Agents**: Web scrapers for different platforms
- **Storage**: SQLite database with time-series observations
- **Scoring**: Multi-factor opportunity scoring
- **Alerts**: Discord/Email notifications
- **API**: RESTful interface
- **Orchestrator**: Job scheduling and coordination

## 📊 Scoring System

### Composite Score Formula

```
Composite = (Velocity × 0.35) + (Margin × 0.30) + (Saturation × 0.35)
```

### Score Interpretation

- **80-100**: 🔥🔥🔥 Strong Buy - Act now!
- **65-79**: 🔥 Buy - Good opportunity
- **50-64**: 👀 Watch - Monitor closely
- **35-49**: ⚠️ Pass - Not ideal timing
- **0-34**: ❌ Too Late - Already saturated

## 🛠️ Development

### Project Structure

```
tiktok-product-scout/
├── src/
│   ├── agents/          # Data collection agents
│   ├── scoring/         # Opportunity scoring
│   ├── storage/         # Database models and operations
│   ├── alerts/          # Notification systems
│   ├── api/             # REST API
│   ├── orchestrator/    # Job scheduling
│   └── utils/           # Utilities
├── tests/               # Unit tests
├── config/              # Configuration files
├── data/                # Data storage
├── scripts/             # Setup and utility scripts
└── docker/              # Docker configuration
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff src/

# Type checking
mypy src/
```

## 🔒 Anti-Detection Features

- Browser fingerprinting randomization
- User agent rotation
- Proxy support
- Random delays and human-like behavior
- Stealth JavaScript injection

## 📈 Performance

- Handles 1000+ products efficiently
- Scheduled scraping intervals prevent rate limiting
- SQLite optimized for time-series queries
- Async operations for concurrent scraping

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes. Please respect the Terms of Service of all platforms you scrape. Use responsibly and ethically.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Web automation with [Playwright](https://playwright.dev/)
- Scheduling with [APScheduler](https://apscheduler.readthedocs.io/)

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: [your-email@example.com](mailto:your-email@example.com)

## 🗺️ Roadmap

### Phase 1: MVP ✅
- [x] Core scraping agents
- [x] Scoring engine
- [x] Alerting system
- [x] API endpoints

### Phase 2: Enhancements
- [ ] Creator tracking and analysis
- [ ] Machine learning score prediction
- [ ] Web dashboard (Streamlit/React)
- [ ] Advanced analytics and charts

### Phase 3: Scale
- [ ] Redis caching
- [ ] Distributed scraping
- [ ] Multi-region support
- [ ] Advanced anti-detection

---

**Made with ❤️ for dropshippers and e-commerce entrepreneurs**
