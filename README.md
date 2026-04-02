# Dodge AI — SAP O2C Context Graph System

A production-grade graph intelligence platform that transforms fragmented SAP Order-to-Cash data into an interactive, queryable knowledge graph. Natural language questions are answered by a three-stage LLM pipeline (classify → generate SQL → verify) backed by a hybrid SQLite + NetworkX data layer.

---

## Live Demo

| Service | URL |
|---|---|
| Frontend | Deployed on Vercel |
| Backend API | Deployed on Render |
| API Docs | `<render-url>/docs` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React Frontend  (Vercel)                    │
│                                                                │
│   force-graph-2d canvas       Chat Panel (SSE streaming)      │
│   - Node expand / inspect      - Natural language input        │
│   - Degree-weighted sizing     - Thought process display       │
│   - Type-coloured nodes        - SQL transparency              │
│   - Anomaly overlay            - Entity highlighting           │
└────────────────────────────┬─────────────────────────────────┘
                             │  REST + Server-Sent Events
┌────────────────────────────┴─────────────────────────────────┐
│                   FastAPI Backend  (Render)                    │
│                                                                │
│   /api/graph          /api/chat            /api/ingest         │
│   - initial nodes     - SSE stream         - JSONL upload      │
│   - expand / focal    - non-stream         - folder ingest     │
│   - search            - session routing    - reset / preview   │
│   - anomalies                                                  │
│   - stats                                                      │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐    │
│   │               3-Stage LLM Pipeline                   │    │
│   │                                                       │    │
│   │  Stage 1: Domain Classifier                          │    │
│   │    Offline keyword scorer → OpenAI GPT-4o-mini       │    │
│   │    Blocks off-topic, extracts entity IDs             │    │
│   │                                                       │    │
│   │  Stage 2: SQL Generator (self-correcting, 2 retries) │    │
│   │    Schema-injected prompt → SELECT query             │    │
│   │    Retry loop with error feedback                    │    │
│   │                                                       │    │
│   │  Stage 3: Result Verifier                            │    │
│   │    NL answer grounded in actual rows                 │    │
│   │    Entity ID extraction for graph highlighting       │    │
│   └──────────────────────────────────────────────────────┘    │
│                                                                │
│   ┌─────────────────────┐   ┌──────────────────────────────┐  │
│   │  SQLite  (17 tables) │   │  NetworkX DiGraph (in-memory)│  │
│   │  1,634 O2C records   │   │  669 nodes  ·  1,188 edges   │  │
│   │  Full join-path SQL  │   │  Degree centrality + BFS     │  │
│   └─────────────────────┘   └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend framework | React 18 + TypeScript | UI |
| Build tool | Vite 5 | Fast dev server + optimised build |
| Styling | Tailwind CSS | Utility-first design |
| Graph visualisation | react-force-graph-2d | Canvas-based force-directed layout |
| State management | Zustand | Lightweight client state |
| Streaming | Fetch + ReadableStream (SSE) | Real-time chat events |
| Backend framework | FastAPI | Async REST API |
| LLM (primary) | OpenAI GPT-4o-mini | Classify, generate SQL, verify |
| LLM (fallback) | Google Gemini 2.0 Flash | Optional secondary provider |
| Relational store | SQLite + aiosqlite | O2C transactional data |
| Graph engine | NetworkX DiGraph | In-memory graph operations |
| Validation | Pydantic v2 | Request/response models + SQL safety |
| Config | pydantic-settings | Typed env-var management |
| Frontend host | Vercel | CDN + SPA routing |
| Backend host | Render | Dockerised web service + persistent disk |
| Container | Docker | Reproducible backend environment |

---

## Data Model

### Node Types (8)

| Node | ID Format | Key Properties |
|---|---|---|
| `Customer` | `CUST_3xxxxxxxx` | name, category, grouping |
| `SalesOrder` | `SO_7xxxxx` | amount (INR), delivery status, payment terms |
| `DeliveryDoc` | `DEL_8xxxxxxx` | shipping point, goods movement status |
| `BillingDoc` | `BILL_9xxxxxxx` | type (F2=invoice / S1=cancellation), amount |
| `JournalEntry` | `JE_94xxxxxxxx` | posting date, amount, clearing date |
| `Payment` | `PAY_9xxxxxxx` | clearing date, amount |
| `Product` | `PROD_xxxxxxx` | description, type, weight |
| `Plant` | `PLANT_xxxx` | name, sales organisation |

### Edge Types (10)

| Edge | Direction | Meaning |
|---|---|---|
| `PLACED` | Customer → SalesOrder | Customer initiated order |
| `CONTAINS_ITEM` | SalesOrder → Product | Line item product |
| `SHIPS_FROM` | SalesOrder → Plant | Originating plant |
| `FULFILLED_BY` | SalesOrder → DeliveryDoc | Delivery fulfils order |
| `BILLED_IN` | DeliveryDoc → BillingDoc | Delivery invoiced |
| `BILLED_BY` | Customer → BillingDoc | Customer billed |
| `POSTED_TO` | BillingDoc → JournalEntry | Invoice posted to GL |
| `CANCELLED` | BillingDoc(S1) → BillingDoc(F2) | Cancellation reference |
| `CLEARED_BY` | JournalEntry → Payment | Payment clears journal |
| `SHIPPED_FROM` | DeliveryDoc → Plant | Shipping plant |

### Critical Join Paths (O2C chain)

```
SalesOrder
  outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder
    DeliveryDoc
      billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument
        BillingDoc
          billing_document_headers.accountingDocument = journal_entry_items.accountingDocument
            JournalEntry
              journal_entry_items.clearingAccountingDocument = payments.clearingAccountingDocument
                Payment
```

---

## LLM Pipeline

### Stage 1 — Domain Classifier

- Fast offline scorer: 34 O2C-domain signals vs 51 off-topic signals, confidence ratio determines guardrail activation.
- LLM fallback (GPT-4o-mini): returns `is_relevant`, `query_type`, `extracted_ids`, `confidence`.
- Query types: `lookup`, `trace`, `anomaly`, `aggregate`, `comparison`, `off_topic`.

### Stage 2 — SQL Generator (self-correcting)

- Full schema context (17 tables, all columns, join paths) injected into system prompt.
- Explicit disambiguation notes (e.g., `billing_document_items.referenceSdDocument` references delivery, not sales order).
- On execution failure or zero-row result: retry prompt includes the failed SQL and error, up to 2 retries.
- Safety: Pydantic validator blocks any non-SELECT statement before execution.

### Stage 3 — Result Verifier

- GPT-4o-mini reads the raw rows and generates a grounded natural-language answer.
- Entity IDs extracted from result rows, merged with IDs from the original query, returned as `highlighted_node_ids` for graph overlay.
- Offline fallback formatter for zero-cost structured output when LLM is unavailable.

---

## Guardrails

| Layer | Mechanism |
|---|---|
| Input validation | Pydantic: max 2000 chars, prompt-injection pattern detection |
| Domain gating | Offline keyword scorer + LLM classifier; off-topic blocked before SQL generation |
| SQL safety | Allowlist: SELECT only. Blocklist: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, EXEC, `--`, `;--` |
| Output grounding | Answer derived solely from query result rows; no hallucinated data |

---

## API Reference

### Graph endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/graph/initial` | Top nodes by degree centrality (`?limit=`) |
| GET | `/api/graph/expand/{node_id}` | Paginated 1-hop neighbours (`?offset=&limit=&exclude=`) |
| GET | `/api/graph/focal/{node_id}` | Focal node + immediate neighbours |
| GET | `/api/graph/node/{node_id}` | Node metadata + neighbour count |
| GET | `/api/graph/search` | Full-text search, returns best-match subgraph (`?q=`) |
| GET | `/api/graph/anomalies` | Incomplete O2C flows (delivered-not-billed, billed-not-posted, cancellations) |
| GET | `/api/graph/stats` | Node/edge counts by type |

### Chat endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat/stream` | SSE streaming pipeline (classify → SQL → execute → answer) |
| POST | `/api/chat/query` | Non-streaming equivalent |

### Ingest endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/ingest/folder` | Ingest JSONL from a server-side folder path |
| POST | `/api/ingest/upload` | Upload JSONL files directly |
| POST | `/api/ingest/reset` | Re-ingest the default dataset |
| GET | `/api/ingest/status` | Current ingestion state |
| GET | `/api/ingest/preview` | Preview folder contents |
| GET | `/api/ingest/browse` | Browse available data folders |

### Utility

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info |
| GET | `/health` | Liveness: graph node/edge counts |
| GET | `/docs` | Interactive Swagger UI |

---

## Why SQLite + NetworkX instead of Neo4j

| Criterion | SQLite + NetworkX | Neo4j |
|---|---|---|
| Infrastructure | Zero — file-based, single process | Requires a running server |
| Data ingestion | JSONL → relational rows is natural for O2C | Needs Cypher ETL |
| Analytical queries | Full SQL with complex joins and aggregations | Cypher excels at traversals, weaker on aggregations |
| Graph operations | NetworkX: degree centrality, BFS, subgraph extraction | Native graph algorithms |
| Scale fit | 669 nodes is trivial for in-memory | Overkill; adds ops burden |
| Deployment | Docker single container, no sidecar | Needs separate container or managed service |

The hybrid approach gives relational power for LLM-driven SQL queries and graph semantics for visualisation and traversal — without adding operational overhead.

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set OPENAI_API_KEY

# Place JSONL data files under backend/data/sap-o2c-data/
# (or use the API to ingest after startup)

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server ingests JSONL data, builds the SQLite schema, constructs the NetworkX graph, and generates the LLM schema context — all at startup.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# VITE_API_BASE_URL defaults to /api (proxied to localhost:8000 in dev)
npm run dev
```

### Docker Compose (full stack)

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Deployment

### Vercel — Frontend

1. Import this repository in Vercel.
2. Vercel detects `vercel.json` and builds `frontend/` automatically.
3. Add one environment variable in the Vercel project settings:

   ```
   VITE_API_BASE_URL=https://<your-render-service>.onrender.com/api
   ```

4. Deploy. SPA client-side routing is handled by the `rewrites` rule in `vercel.json`.

### Render — Backend

1. Create a **Web Service** from this repository.
2. Render detects `render.yaml` — it will build and run the Docker container from `backend/Dockerfile`.
3. Attach a **Persistent Disk** (1 GB minimum) mounted at `/var/data`.
4. Set environment variables in the Render dashboard:

   | Variable | Value |
   |---|---|
   | `OPENAI_API_KEY` | Your OpenAI key |
   | `CORS_ORIGINS` | `https://<your-vercel-app>.vercel.app` |
   | `DATABASE_PATH` | `/var/data/o2c.db` (already set in render.yaml) |
   | `DATA_DIR` | `/var/data/sap-o2c-data` (already set in render.yaml) |

5. On first boot, the service will attempt to ingest JSONL data from `DATA_DIR`. Either:
   - Copy your JSONL files to the persistent disk before the first deploy via Render's shell, or
   - Use the `/api/ingest/upload` endpoint after deploy to push data through the browser.

---

## Example Queries

**Aggregate**
```
Which products are associated with the highest number of billing documents?
```
Joins `products` → `sales_order_items` → `outbound_delivery_items` → `billing_document_items`, groups by product.

**Full O2C trace**
```
Trace the complete flow for billing document 90504248
```
LEFT JOINs from `billing_document_headers` through `journal_entry_items` to `payments`, showing every step and any gaps.

**Anomaly detection**
```
Show sales orders that were delivered but never billed
```
LEFT JOIN `outbound_delivery_headers` → `billing_document_items` WHERE billing columns IS NULL.

**Customer lookup**
```
What are all the orders placed by customer 320000083?
```
Joins `business_partners` → `sales_order_headers` with full order status.

---

## Dataset Statistics

| Metric | Value |
|---|---|
| Total records ingested | 1,634 |
| Graph nodes | 669 |
| Graph edges | 1,188 |
| Customers | 8 |
| Products | 69 |
| Plants | 44 |
| Sales Orders | 100 |
| Delivery Documents | 86 |
| Billing Documents | 163 |
| Journal Entries | 123 |
| Payments | 76 |
| Data date range | March 31 – July 24, 2025 |
| Anomalies detected | 110 |

---

## Project Structure

```
dodge-ai-graph/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI app + lifespan startup
│   │   ├── config.py                Typed settings via pydantic-settings
│   │   ├── models/
│   │   │   ├── chat_models.py       Chat request/response Pydantic models
│   │   │   └── graph_models.py      Graph API response models
│   │   ├── routers/
│   │   │   ├── chat.py              /api/chat  (stream + query)
│   │   │   ├── graph.py             /api/graph (nodes, edges, search, anomalies)
│   │   │   └── ingest.py            /api/ingest (upload, folder, reset)
│   │   ├── services/
│   │   │   ├── llm_agent.py         3-stage NL→SQL pipeline + SSE streaming
│   │   │   ├── guardrails.py        Offline domain classifier
│   │   │   ├── graph_builder.py     JSONL→SQLite ingestion + NetworkX construction
│   │   │   ├── graph_service.py     Graph query helpers (expand, focal, search)
│   │   │   └── sql_executor.py      Safe SELECT execution + entity ID extraction
│   │   └── db/
│   │       └── schema_context.json  Generated schema fed to the LLM prompt
│   ├── data/                        SQLite DB + JSONL source files (persistent disk on Render)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/client.ts            Typed fetch wrappers + SSE parser
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx        Streaming chat UI
│   │   │   ├── Neo4jGraph.tsx       Force-graph canvas + interaction
│   │   │   ├── NodeInspector.tsx    Node metadata side panel
│   │   │   ├── DataIngestionPanel.tsx  Upload + ingest controls
│   │   │   ├── SourcesCitation.tsx  SQL table provenance display
│   │   │   └── ThoughtProcess.tsx   LLM reasoning steps display
│   │   ├── hooks/
│   │   │   ├── useChat.ts           Zustand chat store
│   │   │   └── useGraph.ts          Zustand graph store
│   │   ├── types/graph.ts           TypeScript interfaces
│   │   └── utils/graphColors.ts     Node type → colour mapping
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── render.yaml                      Render deployment spec
├── vercel.json                      Vercel build + SPA routing config
└── README.md
```
