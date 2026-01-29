Markdown

<div align="center">

# 🍕 AI Restaurant Ordering System

### High-Concurrency Voice Order Processing with Hybrid Architecture

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<p align="center">
  <strong>A production-grade backend system demonstrating high-concurrency order processing, race condition prevention, and seamless Mock/Real API switching for AI-powered restaurant phone ordering.</strong>
</p>

<p align="center">
  <a href="#-the-challenge">The Challenge</a> •
  <a href="#-the-solution">The Solution</a> •
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-endpoints">API Docs</a> •
  <a href="#-chaos-simulation">Testing</a>
</p>

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="line" width="100%">

</div>

## 📸 Dashboard Preview

<div align="center">
  <img src="docs/dashboard-preview.png" alt="Dashboard" width="100%">
  <p><em>Real-time dashboard with live order tracking and interactive maps</em></p>
</div>

---

## 🎯 The Challenge

When building an AI voice ordering system for restaurants, a critical problem emerges during peak hours:

> **What happens when 50+ customers call simultaneously during the lunch rush?**

Each order triggers multiple operations:

- 📍 **Address Validation** (Google Maps API)
- 💳 **Payment Processing** (Stripe API)
- 💾 **Database Write** (PostgreSQL)
- 📊 **Excel Export** (for daily reports)

### ❌ Without Proper Handling (Race Conditions)

12:00:01 PM → Order #1 opens Excel file
12:00:01 PM → Order #2 opens Excel file (SAME TIME!)
12:00:01 PM → Order #1 writes data, saves file
12:00:01 PM → Order #2 writes data, saves file → OVERWRITES Order #1!
12:00:02 PM → Order #3 tries to open → FILE LOCKED → CRASH!

Result: Corrupted data, lost orders, system failure 💥

text

---

## ✅ The Solution

This project implements a **production-grade architecture** that handles high concurrency gracefully using industry-standard patterns:
┌─────────────────────────────────────────────────────────────────┐
│ 50+ SIMULTANEOUS ORDERS │
│ (Phone Calls via Vapi.ai Voice Assistant) │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────┐
│ FastAPI │ ← Async, non-blocking
│ HTTP Server │ ← Instant response
└─────────────────┘
│
┌───────────────┼───────────────┐
▼ ▼ ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ Payment │ │ Geo │ │ PostgreSQL│
│ Service │ │ Service │ │ Database │
│Mock/Stripe│ │Mock/Google│ │ (ACID) │
└───────────┘ └───────────┘ └───────────┘
│
▼
┌─────────────────┐
│ Redis Queue │ ← FIFO ordering
│ (Message │ ← Guaranteed delivery
│ Broker) │
└─────────────────┘
│
▼
┌─────────────────┐
│ Celery Worker │ ← Sequential processing
│ (Background │ ← Automatic retry
│ Task Runner) │
└─────────────────┘
│
▼
┌─────────────────┐
│ FileLock │ ← Mutex (one writer)
│ (Mutex) │ ← 30s timeout
└─────────────────┘
│
▼
┌─────────────────┐
│ Excel File │ ← Perfect integrity
│ (orders.xlsx) │ ← Zero corruption
└─────────────────┘

text

### 🔑 Key Components

| Component           | Purpose               | Why It Matters                       |
| ------------------- | --------------------- | ------------------------------------ |
| **FastAPI (Async)** | HTTP request handling | Non-blocking I/O for high throughput |
| **Redis Queue**     | Task serialization    | Orders processed in sequence         |
| **Celery Workers**  | Background processing | API responds instantly               |
| **FileLock**        | File mutex            | Only ONE process writes at a time    |
| **Hybrid Services** | Mock/Real switching   | Development without API costs        |

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🚀 Performance

- **50+ concurrent requests** handled seamlessly
- **Sub-second response times** under load
- **Zero data corruption** guaranteed
- **Automatic retry** on failures

</td>
<td width="50%">

### 🔒 Reliability

- **Race condition prevention** via FileLock
- **Task queue** for ordered processing
- **ACID compliance** with PostgreSQL
- **Graceful error handling**

</td>
</tr>
<tr>
<td width="50%">

### 🔄 Hybrid Architecture

- **Mock services** for development (no API keys)
- **Real APIs** for production (Stripe, Google, Vapi)
- **One environment variable** to switch modes
- **Identical code paths** for both modes

</td>
<td width="50%">

### 📊 Dashboard

- **Real-time statistics** (revenue, orders, rates)
- **Live order feed** with auto-refresh
- **Expandable order details**
- **Interactive delivery maps**

</td>
</tr>
</table>

---

## 🏗️ Architecture

### Hybrid Service Pattern

The system automatically selects Mock or Real services based on configuration:

````python
# .env configuration
ENV_MODE=development  # Uses mock services (free, offline)
ENV_MODE=production   # Uses real APIs (Stripe, Google, Vapi)
Python

# Code is identical - factory pattern handles the switch
from app.services.payment import get_payment_service
from app.services.geo import get_geo_service

payment = get_payment_service()  # → MockPaymentService or StripePaymentService
geo = get_geo_service()          # → MockGeoService or GoogleGeoService
Project Structure
text

ai-restaurant-backend/
│
├── 📁 app/                          # Main application
│   ├── 📁 core/                     # Configuration
│   │   ├── __init__.py
│   │   └── config.py                # Environment & settings
│   │
│   ├── 📁 services/                 # Business logic (hybrid pattern)
│   │   ├── 📁 payment/              # Payment processing
│   │   │   ├── __init__.py          # Factory: get_payment_service()
│   │   │   ├── base.py              # Abstract interface
│   │   │   ├── mock.py              # Mock implementation
│   │   │   └── stripe.py            # Stripe implementation
│   │   │
│   │   ├── 📁 geo/                  # Address validation
│   │   │   ├── __init__.py          # Factory: get_geo_service()
│   │   │   ├── base.py              # Abstract interface
│   │   │   ├── mock.py              # Mock implementation
│   │   │   └── google.py            # Google Maps implementation
│   │   │
│   │   ├── 📁 voice/                # Voice AI integration
│   │   │   ├── __init__.py
│   │   │   ├── vapi_handler.py      # Webhook processing
│   │   │   └── vapi_schemas.py      # Payload models
│   │   │
│   │   ├── __init__.py
│   │   └── excel_manager.py         # Thread-safe Excel ops
│   │
│   ├── 📁 templates/                # Frontend
│   │   └── dashboard.html           # Professional dashboard
│   │
│   ├── __init__.py
│   ├── main.py                      # FastAPI application
│   ├── models.py                    # SQLAlchemy models
│   ├── schemas.py                   # Pydantic schemas
│   ├── database.py                  # Database connection
│   ├── celery_worker.py             # Celery configuration
│   └── tasks.py                     # Background tasks
│
├── 📁 scripts/                      # Utility scripts
│   ├── simulate.py                  # Chaos simulation
│   └── verify.py                    # Data verification
│
├── 📁 docs/                         # Documentation
│   └── architecture.md              # System architecture
│
├── 📁 data/                         # Excel exports (gitignored)
│   └── .gitkeep
│
├── .env.example                     # Environment template
├── .gitignore                       # Git ignore rules
├── docker-compose.yml               # PostgreSQL + Redis
├── requirements.txt                 # Python dependencies
├── LICENSE                          # MIT License
└── README.md                        # This file
🚀 Quick Start
Prerequisites
Requirement	Version
Python	3.10 or higher
Docker	Latest
Docker Compose	Latest
Git	Latest
Step 1: Clone Repository
Bash

git clone https://github.com/Khalil-Bannouri/ai-restaurant-backend.git
cd ai-restaurant-backend
Step 2: Start Infrastructure
Bash

docker-compose up -d
This starts:

🐘 PostgreSQL 15 on port 5433
🔴 Redis 7 on port 6379
Step 3: Setup Python Environment
Bash

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
Step 4: Configure Environment
Bash

# Copy example config
cp .env.example .env

# Default settings work for development (no changes needed)
Step 5: Start the Application
You need two terminal windows:

Terminal 1 - API Server:

Bash

uvicorn app.main:app --reload --port 8001
Terminal 2 - Background Worker:

Bash

celery -A app.celery_worker worker --loglevel=info --pool=solo
Step 6: Access the System
URL	Description
http://localhost:8001	API Root
http://localhost:8001/docs	Interactive API Documentation
http://localhost:8001/dashboard	Real-time Dashboard
http://localhost:8001/health	System Health Check
🔌 API Endpoints
Core Endpoints
Method	Endpoint	Description
GET	/	API information & navigation
GET	/health	System health check (DB, Redis, services)
GET	/docs	Swagger/OpenAPI documentation
GET	/redoc	ReDoc documentation
Order Management
Method	Endpoint	Description
POST	/api/orders	Create new order
GET	/api/orders	List orders (paginated)
GET	/api/orders/{id}	Get order details
Webhooks
Method	Endpoint	Description
POST	/webhook/vapi	Vapi.ai production webhook
POST	/webhook/simulation	Local testing webhook
Dashboard
Method	Endpoint	Description
GET	/dashboard	Dashboard UI
GET	/api/dashboard-data	Dashboard statistics API
Example: Create Order
Bash

curl -X POST http://localhost:8001/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Doe",
    "customer_phone": "555-123-4567",
    "delivery_address": "350 Fifth Avenue",
    "city": "New York",
    "zip_code": "10001",
    "items": [
      {"name": "Pizza Margherita", "quantity": 2, "unit_price": 14.99},
      {"name": "Coke", "quantity": 2, "unit_price": 2.99}
    ]
  }'
🔥 Chaos Simulation
Test the system's ability to handle high concurrency:

Run Simulation
Bash

# Full simulation (50 mixed orders)
python scripts/simulate.py

# Direct API only
python scripts/simulate.py --direct

# Vapi webhook simulation only
python scripts/simulate.py --vapi

# Custom order count
python scripts/simulate.py --orders 100

# Skip pre-flight tests
python scripts/simulate.py --skip-tests
Expected Results
text

======================================================================
🔥 CHAOS SIMULATION - HIGH CONCURRENCY TEST
======================================================================
📋 Total Orders: 50
🎯 Target: http://localhost:8001
🔧 Mode: both
⏰ Started: 12:30:45
======================================================================

🚀 Firing Mixed orders (Direct + Vapi)...

======================================================================
📊 SIMULATION RESULTS
======================================================================

✅ Successful Orders: 44/50
❌ Failed Orders: 6/50
⏱️  Total Time: 1.87s

📡 Direct API: 19/25 successful
🎤 Vapi Simulation: 25/25 successful

📈 Performance Metrics:
   Average Response: 0.94s
   Fastest: 0.57s
   Slowest: 1.50s
   💰 Total Revenue: $2,353.89

⚠️  Failed Order Details (showing first 5):
   Order #7 [direct]: Payment declined (simulated)
   Order #19 [direct]: Card expired (simulated)
   Order #23 [direct]: Geo service timeout (simulated)
======================================================================
Note: Failed orders are expected behavior - they demonstrate the system's graceful error handling. Mock services simulate real-world failure rates (10% payment decline, 5% geo timeout).

Verify Data Integrity
Bash

python scripts/verify.py
text

======================================================================
🔍 EXCEL VERIFICATION REPORT
======================================================================
✅ File loaded successfully!

📊 STATISTICS:
   Total Orders: 44
   Columns: 17

✅ All required columns present
✅ No duplicate order IDs

💰 REVENUE:
   Total: $2,353.89
   Average: $53.50

======================================================================
✅ VERIFICATION COMPLETE - Zero data corruption
======================================================================
🛠️ Tech Stack
Core Technologies
Category	Technology	Purpose
Language	Python 3.10+	Modern async support
Framework	FastAPI	High-performance async API
Database	PostgreSQL 15	ACID-compliant persistence
Queue	Redis 7	Message broker
Worker	Celery 5.4	Distributed task processing
ORM	SQLAlchemy 2.0	Async database operations
Validation	Pydantic 2.0	Data validation & serialization
Excel	Pandas + OpenPyXL	Data export
Locking	FileLock	Race condition prevention
Containers	Docker Compose	Infrastructure
Frontend
Technology	Purpose
Vanilla JS	Dashboard interactivity
Leaflet.js	Interactive delivery maps
Font Awesome	Icons
Inter Font	Typography
Production Integrations (Ready to Enable)
Service	Purpose	Status
Stripe	Payment processing	✅ Integrated
Google Maps	Address geocoding	✅ Integrated
Vapi.ai	AI voice assistant	✅ Integrated
⚙️ Configuration
Environment Variables
Create a .env file based on .env.example:

Bash

# ==============================================================================
# ENVIRONMENT MODE
# ==============================================================================
# development = Mock services (no API keys needed)
# staging     = Real APIs with test keys
# production  = Real APIs with live keys
ENV_MODE=development
DEBUG=true

# ==============================================================================
# DATABASE
# ==============================================================================
DATABASE_URL=postgresql+psycopg://restaurant_admin:secretpassword123@localhost:5433/restaurant_orders

# ==============================================================================
# REDIS
# ==============================================================================
REDIS_URL=redis://localhost:6379/0

# ==============================================================================
# STRIPE (Production only)
# ==============================================================================
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx

# ==============================================================================
# GOOGLE MAPS (Production only)
# ==============================================================================
GOOGLE_MAPS_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxx

# ==============================================================================
# VAPI.AI (Production only)
# ==============================================================================
VAPI_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VAPI_WEBHOOK_SECRET=your-webhook-secret

# ==============================================================================
# BUSINESS SETTINGS
# ==============================================================================
RESTAURANT_NAME="AI Pizza Palace"
TAX_RATE=0.08875
DELIVERY_FEE=5.99
📈 Performance Benchmarks
Tested on a standard development machine:

Metric	Result
Concurrent Requests	50+
Success Rate	88%+ (12% simulated failures)
Average Response Time	0.94 seconds
Fastest Response	0.57 seconds
Slowest Response	1.50 seconds
Data Corruption	0%
Duplicate Orders	0
Total Processing Time	1.87 seconds (for 50 orders)
🔮 Production Deployment
For production deployment, consider:

Scaling Recommendations
Component	Recommendation
API	Multiple Uvicorn workers behind nginx
Celery	Multiple workers with prefork pool
Redis	Redis Cluster or AWS ElastiCache
PostgreSQL	Connection pooling (PgBouncer)
File Storage	Replace Excel with S3/Cloud Storage
Security Checklist
 Use HTTPS in production
 Set DEBUG=false
 Use strong database passwords
 Enable Stripe webhook signature verification
 Configure CORS appropriately
 Use environment-specific API keys
🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

Fork the repository
Create your feature branch (git checkout -b feature/AmazingFeature)
Commit your changes (git commit -m 'Add some AmazingFeature')
Push to the branch (git push origin feature/AmazingFeature)
Open a Pull Request
📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

👤 Author
<div align="center">
Khalil Bannouri
GitHub
LinkedIn

</div>
🙏 Acknowledgments
FastAPI - Modern Python web framework
Celery - Distributed task queue
Redis - In-memory data store
PostgreSQL - Reliable database
Stripe - Payment processing
Vapi.ai - Voice AI platform
Leaflet - Interactive maps
<div align="center">
⭐ If this project helped you, please give it a star!
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="line" width="100%">
Built with ❤️ by Khalil Bannouri

Demonstrating production-grade backend development skills

</div> ```
````
