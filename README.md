# Dodge AI - SAP O2C Context Graph System

A graph-based data modeling and query system that unifies SAP Order-to-Cash (O2C) fragmented data into an interactive graph, with an LLM-powered natural language query interface.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend (Vercel)                │
│  ┌─────────────────┐  ┌───────────────────────────────┐  │
│  │  force-graph-2d  │  │  Chat Interface (SSE)         │  │
│  │  Visualization   │  │  - Natural language input      │  │
│  │  - Node expand   │  │  - Data-backed answers         │  │
│  │  - Metadata      │  │  - Highlighted graph nodes     │  │
│  │  - Search/filter │  │  - Thought process display     │  │
│  └─────────────────┘  └───────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API + SSE
┌───────────────────────┴─────────────────────────────────┐
│                  FastAPI Backend (Render)                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ Graph API    │ │ Query Engine │ │ Guardrails       │  │
│  │ - GET nodes  │ │ - NL → SQL   │ │ - Domain check   │  │
│  │ - GET edges  │ │ - Execute    │ │ - Input validate │  │
│  │ - Expand     │ │ - Format     │ │ - SQL safety     │  │
│  └──────┬───────┘ └──────┬───────┘ └──────────────────┘  │
│         │                │                                │
│         │         ┌──────┴───────┐                        │
│         │         │ Gemini Flash │                        │
│         │         │ (Free Tier)  │                        │
│         │         └──────────────┘                        │
└─────────┼────────────────────────────────────────────────┘
          │
┌─────────┴──────────────────────────────────────────────┐
│         SQLite (relational) + NetworkX (in-memory graph) │
│                                                          │
│  Tables: sales_order_headers, sales_order_items,         │
│  outbound_delivery_headers/items, billing_document       │
│  headers/items, journal_entry_items, payments,           │
│  business_partners, products, plants                     │
│                                                          │
│  NetworkX DiGraph: 669 nodes, 1188 edges                │
└──────────────────────────────────────────────────────────┘
```

## Why SQLite + NetworkX (Not Neo4j)

| Criterion | SQLite + NetworkX | Neo4j |
|---|---|---|
| **Setup** | Zero infrastructure, file-based | Requires server process |
| **Data Ingestion** | JSONL → relational is natural for O2C data | Requires Cypher ETL |
| **Query Power** | Full SQL for complex joins/aggregations | Cypher for traversals |
| **Graph Ops** | NetworkX handles degree centrality, neighbor lookup | Native graph algorithms |
| **Scale** | ~500 nodes is trivial for in-memory | Overkill for this dataset size |
| **Deployment** | Single process, no external deps | Needs Docker/VM |

**Chosen**: SQLite + NetworkX hybrid — relational power for SQL queries, in-memory graph for visualization and traversal operations.

## Graph Data Model

### Node Types (8)
| Node | ID Pattern | Properties |
|------|------------|------------|
| `SalesOrder` | `SO_740506` | totalNetAmount, deliveryStatus, creationDate, paymentTerms |
| `DeliveryDoc` | `DEL_80737721` | shippingPoint, goodsMovementStatus, pickingStatus |
| `BillingDoc` | `BILL_90504248` | type (F2/S1), amount, isCancelled, accountingDocument |
| `JournalEntry` | `JE_9400000220` | postingDate, amount, clearingDate |
| `Payment` | `PAY_9400635977` | clearingDate, amount, customer |
| `Customer` | `CUST_320000083` | fullName, category, grouping |
| `Product` | `PROD_S8907367001003` | description, type, group, weight |
| `Plant` | `PLANT_1920` | plantName, salesOrganization |

### Edge Types (10)
| Edge | From → To | Meaning |
|------|-----------|---------|
| `PLACED` | Customer → SalesOrder | Customer placed the order |
| `CONTAINS_ITEM` | SalesOrder → Product | Order contains product |
| `SHIPS_FROM` | SalesOrder/DeliveryDoc → Plant | Ships from plant |
| `FULFILLED_BY` | SalesOrder → DeliveryDoc | Order fulfilled by delivery |
| `BILLED_IN` | DeliveryDoc → BillingDoc | Delivery billed as invoice |
| `BILLED_BY` | Customer → BillingDoc | Customer billed |
| `POSTED_TO` | BillingDoc → JournalEntry | Invoice posted to accounting |
| `CANCELLED` | BillingDoc(S1) → BillingDoc(F2) | Cancellation reference |
| `CLEARED_BY` | JournalEntry → Payment | Payment clearing |
| `SHIPPED_FROM` | DeliveryDoc → Plant | Shipped from plant |

## LLM Prompting Strategy

### 3-Stage Pipeline

**Stage 1: Domain Classifier**
- Fast offline classifier + optional Gemini LLM
- Checks for domain keywords (sales order, delivery, billing, payment, customer, product, plant)
- Blocks off-topic queries (weather, recipes, jokes, general knowledge)
- Extracts entity IDs (SO numbers, billing docs, customer IDs)
- Returns: `is_relevant`, `query_type`, `extracted_entities`, `confidence`

**Stage 2: SQL Generator**
- Injects full schema context (tables, columns, join paths)
- Critical join paths provided as hints:
  - Order → Delivery: `outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder`
  - Delivery → Billing: `billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument`
  - Billing → Journal: `billing_document_headers.accountingDocument = journal_entry_items.accountingDocument`
- Special note: `billing_document_items.referenceSdDocument` references the **delivery document** (not sales order!)
- SQL safety validation (SELECT only, no mutations)

**Stage 3: Result Verifier**
- Executes SQL against SQLite
- Extracts entity IDs from results for graph highlighting
- Formats answer in natural language (with Gemini) or structured format (offline)

## Guardrails Implementation

### 4 Layers of Protection

1. **Input Validation** (Pydantic validators)
   - Prompt injection detection: blocks `ignore previous instructions`, `act as`, `jailbreak`
   - Max length: 2000 chars

2. **Domain Classifier** (Stage 1)
   - Offline: keyword matching with scoring
   - Online: Gemini LLM classification
   - Off-topic signals: weather, recipes, jokes, math, coding, politics, etc.

3. **SQL Safety Validator** (Pydantic)
   - Only SELECT queries allowed
   - Blocks: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, EXEC
   - Blocks comment syntax: `--`, `;--`

4. **Output Verifier**
   - Results grounded in actual database data
   - Never generates data not in query results
   - Returns "No data found" for empty results

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- Google Gemini API key (free tier at https://ai.google.dev)

### Backend Setup
```bash
cd backend
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy the sap-o2c-data folder into backend/data/
cp -r /path/to/sap-o2c-data data/

# Create .env
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (and OPENAI_API_KEY if desired)

# Ingest data and build graph
python -m app.services.graph_builder

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env
# Optional: set VITE_API_BASE_URL if backend is not proxied locally
npm run dev
```

## Deployment

This repo is set up for:
- Frontend on Vercel
- Backend on Render

### Vercel (Frontend)
1. Import the repo in Vercel.
2. Set the project root to the repository root.
3. Vercel will use [`vercel.json`](vercel.json) and build the frontend from `frontend/`.
4. Add this environment variable in Vercel:
   ```bash
   VITE_API_BASE_URL=https://your-render-backend.onrender.com/api
   ```

### Render (Backend)
1. Create a new Web Service from this repo on Render.
2. Use the following build and start commands:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Attach a persistent disk (minimum 1GB) mounted at `/var/data` so that the SQLite database survives restarts.
4. Add secrets (environment variables):
   ```bash
   GEMINI_API_KEY=your_gemini_key
   OPENAI_API_KEY=your_openai_key  # Optional, used as fallback
   FRONTEND_URL=https://your-vercel-app.vercel.app  # For CORS
   ```
5. Ensure the persistent disk is mounted at `/var/data` and the application will use:
   - Database: `/var/data/o2c.db` (relative path `data/o2c.db` resolves here)
   - Data directory: `/var/data/sap-o2c-data` (if you need to ingest data post-deploy)

Note: The data ingestion step (`python -m app.services.graph_builder`) should be run either:
   a) Before deploying (by copying the data directory into the persistent disk), or
   b) After deploying via Render's shell access (if you prefer to ingest on first run).

## Example Queries

### a. Products with most billing documents
```
Which products are associated with the highest number of billing documents?
```
→ Joins products through sales_order_items → outbound_delivery_items → billing_document_items, GROUP BY product

### b. Full O2C trace
```
Trace the full flow of billing document 90504248
```
→ LEFT JOINs from billing_document_headers through journal_entry_items to payments, showing the complete chain

### c. Incomplete flows
```
Identify sales orders that have broken or incomplete flows (delivered but not billed)
```
→ Uses LEFT JOIN + IS NULL to find delivery records without matching billing documents

## Project Structure
```
dodge-ai-graph/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── models/              # Pydantic models
│   │   ├── routers/             # API endpoints (graph, chat)
│   │   ├── services/            # Business logic
│   │   │   ├── graph_builder.py # JSONL → SQLite + NetworkX
│   │   │   ├── graph_service.py # Graph query operations
│   │   │   ├── llm_agent.py     # NL → SQL pipeline
│   │   │   ├── guardrails.py    # Domain classifier
│   │   │   └── sql_executor.py  # Safe SQL execution
│   │   └── db/                  # Schema context JSON
│   ├── data/                    # SQLite DB + JSONL data (on persistent disk in Render)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── hooks/               # Zustand stores
│   │   ├── types/               # TypeScript interfaces
│   │   ├── utils/               # Color mappings
│   │   └── api/                 # API client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Data Stats
- **Total Records Ingested**: 1,634
- **Graph Nodes**: 669
- **Graph Edges**: 1,188
- **Node Types**: Customer (8), Product (69), Plant (44), SalesOrder (100), DeliveryDoc (86), BillingDoc (163), JournalEntry (123), Payment (76)
- **Date Range**: March 31, 2025 - July 24, 2025
- **Anomalies Found**: 110 (delivered-not-billed, billed-not-posted, billing cancellations)