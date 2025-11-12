# Project Context

## Purpose
PowerMoniter is the backend that ingests high-frequency energy telemetry from edge power-monitoring devices, persists the data in PostgreSQL, and serves a dashboard/API surface for operations teams. It exposes authenticated device APIs for the admin UI, tracks subscriber health, and exports Prometheus metrics for fleet visibility.

## Tech Stack
- Python 3.13 runtime with strict type hints and dataclasses
- Django 5.2 + Django Ninja for the web/API layer (`powermoniter/`, `apps/api/routes/*.py`)
- PostgreSQL via `psycopg` for transactional storage and Django ORM models (`apps/repositories/models.py`)
- MQTT ingestion via `paho-mqtt` subscribers (`apps/subscribers/`)
- Prometheus client for operational metrics (`apps/telemetry/metrics.py`)
- JWT auth built on `pyjwt` and Ninja auth hooks, CORS managed by `django-cors-headers`
- Observability through `sentry-sdk` and structured logging to `logs/django.log`

## Project Conventions

### Code Style
- 4-space indents, Black-compatible formatting, and `from __future__ import annotations` to keep type hints clean.
- Module layout follows `apps/<layer>/` folders (api, schemas, services, repositories, subscribers, telemetry, adapters).
- Public APIs and services include bilingual docstrings, explicit return types, and domain-specific exceptions (`apps/api/errors.py`, `apps/services/device_api_service.py`).
- Prefer dependency-free helpers over utility classes; isolate side effects inside adapters or subscribers.

### Architecture Patterns
- Spec-driven workflow: every net-new capability starts with an OpenSpec change proposal before code.
- Layered boundaries: routes (Ninja routers) delegate to service classes, which orchestrate repositories plus adapters (`apps/services/device_api_service.py`).
- Repository layer is the single source of truth for ORM models; DTOs live in `apps/schemas/` and are the contract for APIs.
- Telemetry ingestion is decoupled via MQTT subscribers that emit Prometheus counters/gauges (`apps/telemetry/metrics.py`) and push data into repositories.

### Testing Strategy
- Targeted unit tests around services and domain helpers; use Django's async test client for API routes.
- Subscriber and adapter code favors contract/fixture tests with synthetic payloads; Prometheus exporters should have regression tests around label changes.
- All new OpenSpec tasks should describe their test coverage; when time-constrained, add TODOs in `tasks.md` so coverage gaps are explicit.

### Git Workflow
- Feature work happens on branches named after the OpenSpec `change-id` (e.g., `add-device-alerting`), merged into `main` via PR after proposal approval.
- Commit messages follow `<change-id>: short summary`, and each PR links back to the proposal and validated spec.
- Never start implementation work on `main`; proposal → approval → branch → implementation → validation is the required order.

## Domain Context
- Devices publish voltage/current/energy readings through MQTT; each reading is tagged with a MAC address and user/device UUID.
- Online/offline status is inferred from last telemetry timestamps; dashboards filter by `DeviceStatusFilter` (`apps/schemas/device_api.py`).
- Electricity usage is surfaced in rolling 24h/7d/30d windows with coarse-grained buckets, so time handling must stay in UTC (`DeviceApiService._WINDOW_CONFIG`).

## Important Constraints
- Enforce JWT auth on every dashboard/API route except explicitly whitelisted health probes.
- Database writes must be idempotent per device timestamp to avoid double-counting when subscribers retry.
- Asia/Shanghai is the system timezone, but persisted timestamps stay UTC; conversions only happen at the edge of the API.
- Production requires Prometheus/Sentry to stay configured; never remove metrics/exceptions without replacements.

## External Dependencies
- PostgreSQL cluster for relational storage.
- MQTT broker for upstream device telemetry ingress.
- Prometheus server scraping `/metrics` for fleet KPIs.
- Sentry project for capturing exceptions and performance traces.
