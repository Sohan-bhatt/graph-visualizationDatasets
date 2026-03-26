import os
import json
import logging
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.config import get_settings
from app.services.graph_builder import (
    ingest_all,
    build_graph,
    generate_schema_context,
    TABLE_MAPPINGS,
    create_tables,
    ingest_folder,
)
from app.services.llm_agent import load_schema_context
import aiosqlite

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])

settings = get_settings()
UPLOAD_DIR = settings.upload_dir
DEFAULT_DATA_DIR = settings.data_dir
DB_PATH = settings.database_path
DATA_ROOT = settings.browse_base_dir


class IngestFolderRequest(BaseModel):
    folder_path: str


class IngestStatus(BaseModel):
    status: str
    message: str
    tables_ingested: dict = {}
    total_records: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0


class DataPreview(BaseModel):
    folder_name: str
    files: list = []
    sample_record: Optional[dict] = None
    record_count_estimate: int = 0


class AvailableFolders(BaseModel):
    folders: list = []
    path: str = ""


def infer_table_folder(name: str) -> str:
    """Infer the canonical ingest folder from a file or folder name."""
    normalized = os.path.basename(name).replace("\\", "/").strip()
    if normalized.endswith(".jsonl"):
        normalized = normalized[:-6]

    if normalized in TABLE_MAPPINGS:
        return normalized

    table_matches = [
        folder_name
        for folder_name, mapping in TABLE_MAPPINGS.items()
        if mapping["table"] == normalized
    ]
    if len(table_matches) == 1:
        return table_matches[0]

    return normalized


def resolve_uploaded_file_path(filename: str) -> str:
    """Map an uploaded filename to the internal folder structure expected by ingest_all."""
    normalized = filename.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part and part not in (".", "..")]

    if not parts:
        raise HTTPException(status_code=400, detail="Invalid uploaded filename")

    if len(parts) == 1:
        table_folder = infer_table_folder(parts[0])
        return os.path.join(UPLOAD_DIR, table_folder, parts[0])

    top_level = infer_table_folder(parts[0])
    return os.path.join(UPLOAD_DIR, top_level, *parts[1:])


@router.post("/folder", response_model=IngestStatus)
async def ingest_from_folder(req: IngestFolderRequest):
    """Ingest JSONL data from a user-specified folder path or file."""
    input_path = req.folder_path

    # Check if it's a single .jsonl file
    if input_path.endswith(".jsonl") and os.path.isfile(input_path):
        # Handle single JSONL file
        os.makedirs(settings.database_dir, exist_ok=True)
        target = DEFAULT_DATA_DIR
        if os.path.islink(target):
            os.unlink(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)
        
        # Determine table name from filename
        table_name = infer_table_folder(input_path)
        table_dir = os.path.join(target, table_name)
        os.makedirs(table_dir, exist_ok=True)
        shutil.copy2(input_path, os.path.join(table_dir, os.path.basename(input_path)))
        
        db_path = DB_PATH
        if os.path.exists(db_path):
            os.remove(db_path)
        total = await ingest_all(db_path, DEFAULT_DATA_DIR)
        G = build_graph(db_path)
        generate_schema_context(db_path)
        load_schema_context()
        
        from app.main import app
        app.state.graph = G
        app.state.db_path = db_path
        
        table_counts = {}
        async with aiosqlite.connect(db_path) as db:
            for table_name_map in TABLE_MAPPINGS.values():
                tname = table_name_map["table"]
                cursor = await db.execute(f"SELECT COUNT(*) FROM {tname}")
                row = await cursor.fetchone()
                table_counts[tname] = row[0]
        
        return IngestStatus(
            status="success",
            message=f"Ingested {total} records from {input_path}",
            tables_ingested=table_counts,
            total_records=total,
            graph_nodes=G.number_of_nodes(),
            graph_edges=G.number_of_edges(),
        )

    # Handle folder path
    if not os.path.isdir(input_path):
        raise HTTPException(status_code=400, detail=f"Folder not found: {input_path}")

    # Check if it contains JSONL subfolders or JSONL files directly
    subdirs = [
        d
        for d in os.listdir(input_path)
        if os.path.isdir(os.path.join(input_path, d))
    ]
    jsonl_files = [
        f for f in os.listdir(input_path) if f.endswith(".jsonl")
    ]

    if not subdirs and not jsonl_files:
        raise HTTPException(
            status_code=400,
            detail="No JSONL files or subdirectories found in the specified folder",
        )

    # Check if this is a single table folder (contains .jsonl directly)
    # or a parent folder with multiple table subfolders
    os.makedirs(settings.database_dir, exist_ok=True)
    target = DEFAULT_DATA_DIR

    # Remove existing symlink/data
    if os.path.islink(target):
        os.unlink(target)
    elif os.path.isdir(target):
        shutil.rmtree(target)

    # If single folder with JSONL files, copy structure
    if jsonl_files and not subdirs:
        # Determine table name from folder name or JSONL filename
        table_name = infer_table_folder(os.path.basename(input_path))
        # Create proper folder structure
        table_dir = os.path.join(target, table_name)
        os.makedirs(table_dir, exist_ok=True)
        logger.info(f"Copying to {table_dir}")
        # Copy JSONL files
        for f in jsonl_files:
            dest_path = os.path.join(table_dir, f)
            shutil.copy2(
                os.path.join(input_path, f),
                dest_path
            )
            logger.info(f"Copied {f} to {dest_path}")
    else:
        # Original behavior - symlink to parent folder
        os.symlink(os.path.abspath(input_path), target)

    # Re-ingest
    db_path = DB_PATH
    if os.path.exists(db_path):
        os.remove(db_path)

    total = await ingest_all(db_path, DEFAULT_DATA_DIR)
    G = build_graph(db_path)
    generate_schema_context(db_path)
    load_schema_context()

    # Update app state graph
    from app.main import app

    app.state.graph = G
    app.state.db_path = db_path

    # Count per table
    table_counts = {}
    async with aiosqlite.connect(db_path) as db:
        for table_name in TABLE_MAPPINGS.values():
            tname = table_name["table"]
            cursor = await db.execute(f"SELECT COUNT(*) FROM {tname}")
            row = await cursor.fetchone()
            table_counts[tname] = row[0]

    return IngestStatus(
        status="success",
        message=f"Ingested {total} records from {input_path}",
        tables_ingested=table_counts,
        total_records=total,
        graph_nodes=G.number_of_nodes(),
        graph_edges=G.number_of_edges(),
    )


@router.post("/upload", response_model=IngestStatus)
async def ingest_from_upload(files: List[UploadFile] = File(...)):
    """Upload JSONL files for ingestion. Files should be organized as folder_name/file.jsonl."""
    if os.path.isdir(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    saved_files = []
    for upload_file in files:
        if not upload_file.filename:
            continue

        safe_path = resolve_uploaded_file_path(upload_file.filename)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)

        content = await upload_file.read()
        with open(safe_path, "wb") as f:
            f.write(content)
        saved_files.append(safe_path)

    if not saved_files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Re-ingest from upload dir
    db_path = DB_PATH
    if os.path.exists(db_path):
        os.remove(db_path)

    total = await ingest_all(db_path, UPLOAD_DIR)
    G = build_graph(db_path)
    generate_schema_context(db_path)
    load_schema_context()

    from app.main import app

    app.state.graph = G
    app.state.db_path = db_path

    return IngestStatus(
        status="success",
        message=f"Ingested {total} records from {len(saved_files)} uploaded files",
        total_records=total,
        graph_nodes=G.number_of_nodes(),
        graph_edges=G.number_of_edges(),
    )


@router.post("/reset", response_model=IngestStatus)
async def reset_and_ingest_default():
    """Reset and re-ingest the default dataset."""
    db_path = DB_PATH
    data_dir = DEFAULT_DATA_DIR

    if not os.path.isdir(data_dir):
        raise HTTPException(
            status_code=400, detail="Default data directory not found"
        )

    if os.path.exists(db_path):
        os.remove(db_path)

    total = await ingest_all(db_path, data_dir)
    G = build_graph(db_path)
    generate_schema_context(db_path)
    load_schema_context()

    from app.main import app

    app.state.graph = G
    app.state.db_path = db_path

    return IngestStatus(
        status="success",
        message=f"Reset and ingested {total} records",
        total_records=total,
        graph_nodes=G.number_of_nodes(),
        graph_edges=G.number_of_edges(),
    )


@router.get("/preview")
async def preview_folder(folder_path: str):
    """Preview what's in a folder before ingesting."""
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")

    subdirs = [
        d
        for d in sorted(os.listdir(folder_path))
        if os.path.isdir(os.path.join(folder_path, d))
    ]

    previews = []
    for subdir in subdirs[:20]:
        subdir_path = os.path.join(folder_path, subdir)
        jsonl_files = sorted(
            [f for f in os.listdir(subdir_path) if f.endswith(".jsonl")]
        )

        sample = None
        count = 0
        for jf in jsonl_files:
            filepath = os.path.join(subdir_path, jf)
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        count += 1
                        if sample is None:
                            try:
                                sample = json.loads(line)
                            except:
                                pass

        previews.append(
            {
                "folder_name": subdir,
                "files": jsonl_files,
                "sample_record": sample,
                "record_count_estimate": count,
            }
        )

    # Also check for JSONL files directly in the root
    root_files = [f for f in os.listdir(folder_path) if f.endswith(".jsonl")]
    if root_files:
        sample = None
        count = 0
        for jf in root_files:
            filepath = os.path.join(folder_path, jf)
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        count += 1
                        if sample is None:
                            try:
                                sample = json.loads(line)
                            except:
                                pass
        previews.insert(
            0,
            {
                "folder_name": "(root)",
                "files": root_files,
                "sample_record": sample,
                "record_count_estimate": count,
            },
        )

    return {"path": folder_path, "folders": previews}


@router.get("/browse")
async def browse_folders(base_path: str = DATA_ROOT):
    """Browse available data folders on the server."""
    folders = []
    base = base_path if os.path.isabs(base_path) else os.path.abspath(base_path)
    
    if os.path.isdir(base):
        for item in sorted(os.listdir(base)):
            item_path = os.path.join(base, item)
            if os.path.isdir(item_path):
                # Check if it has jsonl files or subdirectories with jsonl
                has_data = False
                subfolders = []
                for sub in os.listdir(item_path):
                    sub_path = os.path.join(item_path, sub)
                    if os.path.isdir(sub_path):
                        jsonl_files = [f for f in os.listdir(sub_path) if f.endswith('.jsonl')]
                        if jsonl_files:
                            has_data = True
                            subfolders.append(sub)
                    elif sub.endswith('.jsonl'):
                        has_data = True
                
                if has_data:
                    folders.append({
                        "name": item,
                        "path": item_path,
                        "subfolders": subfolders[:10]  # Limit to 10
                    })
    
    return {"folders": folders, "base_path": base}


@router.get("/status")
async def get_ingest_status():
    """Get current data ingestion status."""
    db_path = DB_PATH

    if not os.path.exists(db_path):
        return {"status": "no_data", "message": "No data ingested yet"}

    from app.main import app

    graph = getattr(app.state, "graph", None)

    table_counts = {}
    try:
        async with aiosqlite.connect(db_path) as db:
            for table_name in TABLE_MAPPINGS.values():
                tname = table_name["table"]
                cursor = await db.execute(f"SELECT COUNT(*) FROM {tname}")
                row = await cursor.fetchone()
                table_counts[tname] = row[0]
    except:
        pass

    return {
        "status": "ready" if graph else "no_graph",
        "tables": table_counts,
        "graph_nodes": graph.number_of_nodes() if graph else 0,
        "graph_edges": graph.number_of_edges() if graph else 0,
    }
