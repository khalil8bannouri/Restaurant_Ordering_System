# System Architecture

## Overview

The Restaurant Ordering System uses a **hybrid architecture** that supports both mock services (for development) and real APIs (for production).

## Architecture Diagram
┌─────────────────────────────────────────────────────────────────────┐
│ CLIENT REQUESTS │
│ (Vapi.ai Voice / Web App / Mobile App) │
└─────────────────────────────────┬───────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────┐
│ FASTAPI SERVER │
│ (Async HTTP Handling) │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ /webhook/ │ │ /api/ │ │ /dashboard │ │
│ │ vapi │ │ orders │ │ │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
│
┌─────────────┴─────────────┐
▼ ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│ SERVICE FACTORY │ │ DATABASE │
│ ┌─────────────────────┐ │ │ PostgreSQL │
│ │ ENV_MODE=development│ │ │ ┌─────────────────────┐ │
│ │ → Mock Services │ │ │ │ Orders Table │ │
│ │ │ │ │ │ - id │ │
│ │ ENV_MODE=production │ │ │ │ - customer_name │ │
│ │ → Real APIs │ │ │ │ - total_amount │ │
│ └─────────────────────┘ │ │ │ - status │ │
└───────────────────────────┘ │ └─────────────────────┘ │
│ └───────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────┐
│ SERVICE LAYER │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ Payment │ │ Geo │ │ Voice │ │
│ │ Service │ │ Service │ │ Handler │ │
│ ├─────────────┤ ├─────────────┤ ├─────────────┤ │
│ │ Mock/Stripe │ │Mock/Google │ │ Vapi.ai │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
└───────────────────────────────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────┐
│ TASK QUEUE │
│ ┌─────────────┐ ┌─────────────┐ │
│ │ Redis │ ──────▶ │ Celery │ │
│ │ Broker │ │ Worker │ │
│ └─────────────┘ └──────┬──────┘ │
└─────────────────────────────────┼─────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────┐
│ FILE SYSTEM │
│ ┌─────────────┐ ┌─────────────┐ │
│ │ FileLock │ ──────▶ │ Excel │ │
│ │ (Mutex) │ │ Export │ │
│ └─────────────┘ └─────────────┘ │
└───────────────────────────────────────────────────────────┘


## Components

### 1. FastAPI Server
- Async HTTP handling for high concurrency
- Automatic OpenAPI documentation
- Request validation with Pydantic

### 2. Service Factory Pattern
- `get_payment_service()` → Returns Mock or Stripe
- `get_geo_service()` → Returns Mock or Google Maps
- Controlled by `ENV_MODE` environment variable

### 3. Task Queue (Redis + Celery)
- Decouples API response from file operations
- Ensures ordered processing of Excel writes
- Automatic retry on failure

### 4. FileLock
- Prevents race conditions on Excel file
- Only one process can write at a time
- 30-second timeout with retry

## Data Flow

1. **Request Received** → FastAPI validates and processes
2. **Services Called** → Payment/Geo validation
3. **Database Write** → Order saved to PostgreSQL
4. **Task Queued** → Excel export sent to Redis
5. **Worker Processes** → Celery picks up task
6. **File Lock Acquired** → Safe Excel write
7. **Response Sent** → Client receives confirmation

## Environment Modes

| Mode | Payment | Geo | Voice | Use Case |
|------|---------|-----|-------|----------|
| `development` | Mock | Mock | Mock | Local testing |
| `staging` | Stripe (test) | Google | Vapi | Pre-production |
| `production` | Stripe (live) | Google | Vapi | Live system |