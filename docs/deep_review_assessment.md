# TikTok Product Scout — Deep Review & Systematic Assessment

## Executive Summary

This codebase is a strong MVP with clear separation between ingestion agents, scoring logic, storage, orchestration, and API delivery. The biggest gains now come from improving **data quality**, **operational reliability**, and **query/runtime efficiency** rather than adding more scraping endpoints immediately.

Top opportunities:

1. Add observability, retries, and idempotency at job level.
2. Improve data model constraints/indexing and dedup logic to reduce noisy matches.
3. Decouple synchronous DB access from async flows and batch expensive API scoring paths.
4. Introduce confidence-aware ranking and trend-shift detection features to increase alert quality.

## What Was Reviewed

- Runtime entrypoints and scheduling
- Agent scraping patterns and stealth/retry hooks
- Storage models and database query patterns
- Scoring algorithms and signal composition
- API endpoint behavior and scaling risk
- Tooling/testing posture

## Systematic Findings

### 1) Architecture & Runtime Control

**Strengths**
- Clear orchestration abstraction (`JobCoordinator`, `JobScheduler`) with explicit phases (scrape → score → alert).
- Config-driven scheduling and thresholds.

**Gaps / Risks**
- Continuous loop and scheduler startup have limited lifecycle/health controls (no readiness/liveness integration, no graceful cancellation path beyond keyboard interrupt).
- Jobs can overlap under scheduler drift; no explicit `max_instances`, coalescing, or misfire handling to prevent pileups.
- Logging is configured globally with a file handler in process startup, but does not enforce structured/contextual fields for correlation IDs.

**Recommended Optimizations**
- Set APScheduler job defaults (`max_instances=1`, `coalesce=True`, `misfire_grace_time`) and per-job execution timeouts.
- Add a job-run UUID and attach to scrape/scoring/alert logs + DB scrape_job rows.
- Introduce graceful shutdown hooks (SIGTERM) for container deployment.

### 2) Data Model, Integrity, and Query Efficiency

**Strengths**
- Clean normalized tables for products, observations, supplier matches, alerts, and scrape jobs.
- Reasonable baseline dedup strategy with exact/fuzzy matching.

**Gaps / Risks**
- No uniqueness guarantees on `(source, source_product_id, observed_at)` or supplier entries, so replayed ingestion can duplicate observations.
- Fuzzy name matching scans category candidate sets in Python; this can degrade with growth and may cause false merges.
- Several high-frequency query paths lack explicit composite indexes aligned to filters/sorts (e.g., score + active + timestamps).

**Recommended Optimizations**
- Add unique constraints and conflict handling (upsert) for ingestion idempotency.
- Move fuzzy candidate selection to a narrowed SQL prefilter (e.g., trigram/normalized prefix buckets), then fuzzy match in memory over small candidate sets.
- Add indexes for alert candidate and scoring workflows:
  - `products(composite_score, is_active, last_updated_at)`
  - `product_observations(product_id, source, observed_at DESC)`
  - `alerts(product_id, sent_at DESC)`

### 3) Async / I/O Behavior

**Strengths**
- Async agent interfaces and async scraping integration with Playwright.

**Gaps / Risks**
- Database layer uses synchronous SQLAlchemy sessions from async coordinator/API contexts; under scale this can block event loop time and reduce throughput.
- API endpoints recompute scores repeatedly and may cause N+1 query patterns (`/opportunities`, `/products/{id}`) when dataset grows.

**Recommended Optimizations**
- Option A (low migration risk): run synchronous DB operations in a dedicated threadpool boundary.
- Option B (strategic): migrate to SQLAlchemy async engine with `async_sessionmaker`.
- Precompute/cache score snapshots and only recompute on demand when stale threshold exceeded.
- Add pagination metadata with total count from SQL instead of len(result-set) only.

### 4) Scoring Quality & Alert Precision

**Strengths**
- Transparent weighted composite scoring with signals and recommendation tiers.
- Confidence signal already exists and can be leveraged further.

**Gaps / Risks**
- Saturation scorer currently estimates creator count heuristically from observations rather than explicit creator telemetry.
- Margin assumptions are static constants; no category/geo/platform dynamic fee modeling.
- Alerting can trigger on single-step score calculation without trend-stability checks, risking noisy alerts.

**Recommended Optimizations**
- Add signal smoothing (EWMA over last N observations) and minimum-confidence gates before “buy/strong_buy” alerts.
- Add category-specific margin defaults and confidence penalties when supplier data quality is low.
- Introduce score-delta alerts (e.g., composite +15 within 24h) and “cooldown by recommendation change” logic.

### 5) Scraping Resilience & Anti-Block Operations

**Strengths**
- Stealth hooks and proxy abstractions are already built in.
- Retry utilities and block-detection hooks are present.

**Gaps / Risks**
- Proxy health is not persisted/weighted, so bad proxies can be repeatedly reused.
- Parser fragility: CSS selectors are tightly coupled to current page DOM contracts.
- Inconsistent exception discipline (bare exceptions in multiple modules) can hide root causes.

**Recommended Optimizations**
- Add proxy scorecard (success rate, latency, last failure reason), and weighted selection with cooldown quarantine.
- Implement selector fallback chains and schema validation for extracted payloads.
- Replace bare exceptions with typed catches + contextual logs.

### 6) API, Product Surface, and UX

**Strengths**
- Practical endpoints for listing products, opportunities, rescoring, and health.

**Gaps / Risks**
- No authentication/rate limiting.
- CORS is open to all origins, acceptable for local testing but risky for production.
- API response schemas are hand-built dicts; no typed response models, making compatibility harder to manage.

**Recommended Optimizations**
- Add API key/JWT auth + request throttling.
- Restrict CORS by config in production.
- Define Pydantic response models and versioned API contracts.

### 7) Engineering Quality (Lint/Test/CI)

**Current Signal**
- `pytest -q` reports no tests.
- `ruff check src` reports lint failures including bare exceptions and unused imports.

**Recommended Optimizations**
- Add a testing pyramid:
  - Unit tests for scorers and parsing helpers
  - Contract tests for API schemas
  - Integration tests for DB upsert/scoring/alert workflows
- Enforce CI gates (`ruff`, `pytest`, optional mypy) on pull requests.

## Highest-ROI Roadmap (Prioritized)

### Phase 1 (1–2 weeks): Reliability + Data Integrity
1. Add unique constraints and idempotent upserts for observations/supplier matches.
2. Fix lint-critical exception handling and import hygiene.
3. Add scheduler guardrails (`max_instances`, coalesce, misfire controls).
4. Add minimal unit tests for scorers and parse utilities.

**Expected impact:** fewer duplicate records, lower alert noise, safer continuous operation.

### Phase 2 (2–4 weeks): Performance + API Scalability
1. Remove N+1 scoring patterns in API endpoints (batch fetch observations/supplier matches).
2. Introduce caching/staleness-based rescoring.
3. Add key indexes and query tuning with explain plans.

**Expected impact:** materially better latency and lower CPU cost as dataset grows.

### Phase 3 (4–8 weeks): Feature Differentiation
1. Creator graph tracking for real saturation modeling.
2. Trend-shift detector (velocity inflection + score delta + confidence).
3. Experiment framework for scoring weights per category.

**Expected impact:** better precision/recall for early winners and stronger moat.

## Recommended Feature Adds (Most Effective)

1. **Opportunity Backtesting Module**
   - Replays historical observations and evaluates whether recommendations predicted future growth/margin outcomes.
   - Enables objective calibration of thresholds and weights.

2. **Confidence-Aware Alert Routing**
   - Route high-confidence strong-buy to instant channels; medium-confidence to digest summary.
   - Reduces alert fatigue and increases actionability.

3. **Portfolio View + Watchlists**
   - Group opportunities by category/risk profile with trend trajectories and expected margin bands.
   - Converts raw data into operator decision workflows.

4. **Supplier Diversity Scoring**
   - Score supply-chain fragility by counting distinct suppliers, delivery variance, and rating dispersion.
   - Helps avoid single-supplier failures.

5. **Anomaly and Data Drift Detection**
   - Detect sudden parser failures, metric outliers, and source schema changes before they corrupt scoring.

## Quick Wins You Can Ship Immediately

- Resolve current lint issues and ban bare `except` in the project.
- Add migration for uniqueness/indexes and idempotent write paths.
- Add score confidence threshold to alerting (e.g., confidence >= 0.65).
- Configure production-safe CORS/auth toggles via config.

## Suggested KPIs to Track Post-Optimization

- Ingestion duplicate rate (%)
- Proxy success rate + mean scrape latency
- Alert precision (alerts that become “winners” within X days)
- API p95 latency for `/opportunities` and `/products/{id}`
- Score stability (daily variance for top N products)

---

If you want, the next step can be a concrete implementation PR for **Phase 1** (idempotency constraints + scheduler guardrails + lint/test baseline), which should deliver the fastest measurable reliability improvement.
