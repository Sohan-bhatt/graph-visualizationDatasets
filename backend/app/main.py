import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import graph, chat, ingest
from app.services.graph_builder import ingest_all, build_graph, generate_schema_context
from app.services.llm_agent import load_schema_context, init_llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Dodge AI Context Graph System...")

    db_path = settings.database_path
    data_dir = settings.data_dir
    os.makedirs(settings.database_dir, exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Check if data directory exists
    if not os.path.isdir(data_dir):
        logger.warning(f"Data directory not found: {data_dir}. Skipping initial data ingestion.")
        logger.info("You can trigger data ingestion later via the /ingest endpoint.")
    else:
        # Ingest data
        logger.info("Ingesting JSONL data into SQLite...")
        await ingest_all(db_path, data_dir)

    # Build NetworkX graph (from existing database, which may be empty if no data was ingested)
    logger.info("Building NetworkX graph...")
    graph_obj = build_graph(db_path)

    # Generate schema context for LLM (from existing database)
    logger.info("Generating schema context...")
    generate_schema_context(db_path)

    # Store in app state
    app.state.graph = graph_obj
    app.state.db_path = db_path

    logger.info(
        f"System ready. Graph: {graph_obj.number_of_nodes()} nodes, {graph_obj.number_of_edges()} edges"
        + (" (no data ingested)" if not os.path.isdir(data_dir) else "")
    )

    # Load schema for LLM agent
    load_schema_context()
    init_llm()

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="Dodge AI - Context Graph System",
    description="SAP Order-to-Cash data modeled as a graph with LLM-powered natural language queries",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(ingest.router)


@app.get("/")
async def root():
    return {
        "name": "Dodge AI - Context Graph System",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    graph = getattr(app.state, "graph", None)
    return {
        "status": "ok",
        "graph_loaded": graph is not None,
        "nodes": graph.number_of_nodes() if graph else 0,
        "edges": graph.number_of_edges() if graph else 0,
    }