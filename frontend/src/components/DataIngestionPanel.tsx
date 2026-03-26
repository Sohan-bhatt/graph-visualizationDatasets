import { useState, useEffect, useCallback } from "react";
import { FolderOpen, Upload, RefreshCw, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
import { apiUrl } from "../api/client";

interface IngestStatus {
  status: string;
  message: string;
  tables_ingested: Record<string, number>;
  total_records: number;
  graph_nodes: number;
  graph_edges: number;
}

interface FolderPreview {
  folder_name: string;
  files: string[];
  sample_record: Record<string, unknown> | null;
  record_count_estimate: number;
}

interface DataIngestionPanelProps {
  onIngestComplete: () => void;
}

export default function DataIngestionPanel({ onIngestComplete }: DataIngestionPanelProps) {
  const [folderPath, setFolderPath] = useState("");
  const [preview, setPreview] = useState<FolderPreview[] | null>(null);
  const [status, setStatus] = useState<IngestStatus | null>(null);
  const [currentStatus, setCurrentStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedFolder, setExpandedFolder] = useState<string | null>(null);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [availableFolders, setAvailableFolders] = useState<{name: string, path: string, subfolders: string[]}[]>([]);

  // Load current status and available folders on mount
  useEffect(() => {
    fetchCurrentStatus();
    fetchAvailableFolders();
  }, []);

  const fetchCurrentStatus = async () => {
    try {
      const res = await fetch(apiUrl("/ingest/status"));
      const data = await res.json();
      setCurrentStatus(data);
    } catch {
      setCurrentStatus(null);
    }
  };

  const fetchAvailableFolders = async () => {
    try {
      const res = await fetch(apiUrl("/ingest/browse"));
      const data = await res.json();
      setAvailableFolders(data.folders || []);
    } catch {
      setAvailableFolders([]);
    }
  };

  const handlePreview = async () => {
    if (!folderPath.trim()) return;
    setLoading(true);
    setError("");
    setPreview(null);
    try {
      const res = await fetch(apiUrl(`/ingest/preview?folder_path=${encodeURIComponent(folderPath)}`));
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Preview failed");
      }
      const data = await res.json();
      setPreview(data.folders);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!folderPath.trim()) return;
    setLoading(true);
    setError("");
    setStatus(null);
    try {
      const res = await fetch(apiUrl("/ingest/folder"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_path: folderPath }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Ingestion failed");
      }
      const data: IngestStatus = await res.json();
      setStatus(data);
      await fetchCurrentStatus();
      onIngestComplete();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!uploadFiles || uploadFiles.length === 0) return;
    setLoading(true);
    setError("");
    setStatus(null);

    const formData = new FormData();
    for (let i = 0; i < uploadFiles.length; i++) {
      formData.append("files", uploadFiles[i]);
    }

    try {
      const res = await fetch(apiUrl("/ingest/upload"), {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }
      const data: IngestStatus = await res.json();
      setStatus(data);
      await fetchCurrentStatus();
      onIngestComplete();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    setError("");
    setStatus(null);
    try {
      const res = await fetch(apiUrl("/ingest/reset"), { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Reset failed");
      }
      const data: IngestStatus = await res.json();
      setStatus(data);
      await fetchCurrentStatus();
      onIngestComplete();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: "#0f0f1a",
      border: "1px solid #1e1e2e",
      borderRadius: 12,
      padding: 20,
      color: "#e5e5e5",
      fontFamily: '"Inter", system-ui, sans-serif',
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <FolderOpen size={18} style={{ color: "#3B82F6" }} />
        <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Data Ingestion</h2>
      </div>

      {/* Current Status */}
      {currentStatus && currentStatus.status === "ready" && (
        <div style={{
          background: "#14141f",
          border: "1px solid #1e1e2e",
          borderRadius: 8,
          padding: "10px 14px",
          marginBottom: 16,
          fontSize: 11,
          color: "#888",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <CheckCircle size={12} style={{ color: "#10B981" }} />
            <span style={{ color: "#10B981" }}>Data loaded</span>
          </div>
          <span>{currentStatus.graph_nodes} nodes, {currentStatus.graph_edges} edges</span>
        </div>
      )}

      {/* Section: Available Folders */}
      {availableFolders.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 11, color: "#888", display: "block", marginBottom: 6 }}>
            Available Data Folders (click to select)
          </label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {availableFolders.map((folder) => (
              <button
                key={folder.path}
                onClick={() => {
                  setFolderPath(folder.path);
                  setError("");
                }}
                style={{
                  padding: "8px 14px",
                  background: folderPath === folder.path ? "#1d4ed8" : "#1a1a2e",
                  border: "1px solid #333",
                  borderRadius: 8,
                  color: "#e5e5e5",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                {folder.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Section 1: Folder Path */}
      <div style={{ marginBottom: 20 }}>
        <label style={{ fontSize: 11, color: "#888", display: "block", marginBottom: 6 }}>
          Data Folder Path (contains JSONL subfolders)
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="/path/to/your/sap-o2c-data"
            style={{
              flex: 1,
              background: "#14141f",
              border: "1px solid #252535",
              borderRadius: 8,
              padding: "8px 12px",
              color: "#e5e5e5",
              fontSize: 12,
              outline: "none",
              fontFamily: '"Fira Code", monospace',
            }}
          />
          <button
            onClick={handlePreview}
            disabled={loading || !folderPath.trim()}
            style={{
              padding: "8px 14px",
              background: "#252535",
              border: "1px solid #333",
              borderRadius: 8,
              color: "#aaa",
              fontSize: 11,
              cursor: loading ? "default" : "pointer",
              opacity: loading || !folderPath.trim() ? 0.5 : 1,
            }}
          >
            Preview
          </button>
          <button
            onClick={handleIngest}
            disabled={loading || !folderPath.trim()}
            style={{
              padding: "8px 14px",
              background: "#1d4ed8",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              fontSize: 11,
              fontWeight: 600,
              cursor: loading ? "default" : "pointer",
              opacity: loading || !folderPath.trim() ? 0.5 : 1,
            }}
          >
            {loading ? "Ingesting..." : "Ingest"}
          </button>
        </div>
      </div>

      {/* Preview Results */}
      {preview && (
        <div style={{
          background: "#14141f",
          border: "1px solid #1e1e2e",
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
          maxHeight: 300,
          overflowY: "auto",
        }}>
          <div style={{ fontSize: 11, color: "#888", marginBottom: 8 }}>
            Found {preview.length} subfolder(s)
          </div>
          {preview.map((folder) => (
            <div key={folder.folder_name} style={{ marginBottom: 6 }}>
              <button
                onClick={() => setExpandedFolder(expandedFolder === folder.folder_name ? null : folder.folder_name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: "none",
                  color: "#ddd",
                  fontSize: 12,
                  padding: "6px 0",
                  cursor: "pointer",
                }}
              >
                {expandedFolder === folder.folder_name ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span style={{ fontWeight: 600 }}>{folder.folder_name}</span>
                <span style={{ color: "#666", fontSize: 10 }}>
                  {folder.record_count_estimate} records, {folder.files.length} file(s)
                </span>
              </button>
              {expandedFolder === folder.folder_name && folder.sample_record && (
                <pre style={{
                  fontSize: 10,
                  color: "#888",
                  background: "#0a0a14",
                  borderRadius: 6,
                  padding: 8,
                  marginTop: 4,
                  overflowX: "auto",
                  fontFamily: '"Fira Code", monospace',
                  maxHeight: 150,
                }}>
                  {JSON.stringify(folder.sample_record, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Section 2: File Upload */}
      <div style={{ marginBottom: 20 }}>
        <label style={{ fontSize: 11, color: "#888", display: "block", marginBottom: 6 }}>
          Upload JSONL files
        </label>
        <div style={{ fontSize: 10, color: "#666", marginBottom: 8 }}>
          Single files like <code>payments.jsonl</code> or <code>products.jsonl</code> are supported.
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="file"
            multiple
            accept=".jsonl"
            onChange={(e) => setUploadFiles(e.target.files)}
            style={{
              flex: 1,
              fontSize: 11,
              color: "#888",
            }}
          />
          <button
            onClick={handleUpload}
            disabled={loading || !uploadFiles || uploadFiles.length === 0}
            style={{
              padding: "8px 14px",
              background: "#10B981",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              fontSize: 11,
              fontWeight: 600,
              cursor: loading ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              opacity: loading || !uploadFiles ? 0.5 : 1,
            }}
          >
            <Upload size={12} />
            Upload
          </button>
        </div>
      </div>

      {/* Section 3: Reset */}
      <div style={{ marginBottom: 16 }}>
        <button
          onClick={handleReset}
          disabled={loading}
          style={{
            padding: "8px 14px",
            background: "transparent",
            border: "1px solid #333",
            borderRadius: 8,
            color: "#888",
            fontSize: 11,
            cursor: loading ? "default" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <RefreshCw size={12} />
          Reset to Default Dataset
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 12px",
          background: "rgba(127,29,29,0.15)",
          border: "1px solid #7f1d1d",
          borderRadius: 8,
          fontSize: 11,
          color: "#fca5a5",
          marginBottom: 12,
        }}>
          <AlertCircle size={13} />
          {error}
        </div>
      )}

      {/* Success Status */}
      {status && (
        <div style={{
          background: "#14141f",
          border: "1px solid #10B981",
          borderRadius: 8,
          padding: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <CheckCircle size={14} style={{ color: "#10B981" }} />
            <span style={{ fontSize: 12, color: "#10B981", fontWeight: 600 }}>{status.message}</span>
          </div>
          <div style={{ fontSize: 11, color: "#888" }}>
            Graph: {status.graph_nodes} nodes, {status.graph_edges} edges
          </div>
          {Object.keys(status.tables_ingested).length > 0 && (
            <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
              {Object.entries(status.tables_ingested).map(([table, count]) => (
                <span key={table} style={{
                  fontSize: 9,
                  padding: "2px 6px",
                  background: "#1a1a2a",
                  borderRadius: 6,
                  color: "#888",
                }}>
                  {table}: {count}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
