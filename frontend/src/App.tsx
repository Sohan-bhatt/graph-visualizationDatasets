import { useState, useEffect, useCallback, useMemo } from "react";
import { Search, Database, GitBranch, AlertTriangle, FolderOpen, X } from "lucide-react";
import Neo4jGraph from "./components/Neo4jGraph";
import ChatPanel from "./components/ChatPanel";
import DataIngestionPanel from "./components/DataIngestionPanel";
import { useGraphStore } from "./hooks/useGraph";
import { searchNodes } from "./api/client";
import type { GraphData, NodeData, EdgeData } from "./components/Neo4jGraph";

function App() {
  const {
    nodes,
    edges,
    highlightedNodeIds,
    focalNodeId,
    expansionState,
    isLoading,
    totalNodes,
    totalEdges,
    remainingNodes,
    error,
    loadInitialGraph,
    loadMoreOverview,
    expandNodeNeighbors,
    loadFocalSubgraph,
    highlightNodes,
  } = useGraphStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    { id: string; type: string; label: string; total_neighbors: number }[]
  >([]);
  const [showSearch, setShowSearch] = useState(false);
  const [showDataPanel, setShowDataPanel] = useState(false);

  useEffect(() => {
    loadInitialGraph();
  }, [loadInitialGraph]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await searchNodes(searchQuery);
        setSearchResults(res.results.map((r) => ({ ...r, total_neighbors: r.total_neighbors })));
      } catch {
        setSearchResults([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSearchSelect = useCallback(
    async (nodeId: string) => {
      setShowSearch(false);
      setSearchQuery("");
      setSearchResults([]);
      await loadFocalSubgraph(nodeId);
    },
    [loadFocalSubgraph]
  );

  const handleChatHighlight = useCallback(
    async (ids: string[], focalNodeId?: string) => {
      const targetNodeId = focalNodeId || ids[0];
      if (!targetNodeId) return;
      await loadFocalSubgraph(targetNodeId);
      highlightNodes(ids);
    },
    [loadFocalSubgraph, highlightNodes]
  );

  const handleExpandNode = useCallback(
    (nodeId: string) => {
      expandNodeNeighbors(nodeId);
    },
    [expandNodeNeighbors]
  );

  const handleShowMore = useCallback(() => {
    if (focalNodeId) {
      expandNodeNeighbors(focalNodeId);
      return;
    }
    loadMoreOverview();
  }, [expandNodeNeighbors, focalNodeId, loadMoreOverview]);

  const handleIngestComplete = useCallback(() => {
    useGraphStore.getState().resetGraph();
    loadInitialGraph();
  }, [loadInitialGraph]);

  const graphData: GraphData = useMemo(() => {
    const nodeMap = new Map<string, NodeData>();
    for (const n of nodes) {
      nodeMap.set(n.id, {
        id: n.id,
        type: n.type,
        label: n.label,
        color: "",
        properties: (n.metadata?.properties as Record<string, unknown>) || {},
        degree: n.degree,
        is_anomaly: n.is_anomaly,
      });
    }
    const links: EdgeData[] = edges.map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.relationship,
      properties: e.properties,
    }));
    return { nodes: Array.from(nodeMap.values()), links };
  }, [nodes, edges]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0a0a14", color: "#e5e5e5", fontFamily: '"Inter", system-ui, sans-serif', overflow: "hidden" }}>
      {/* ─── Top Bar ───────────────────────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          height: 44,
          background: "#0f0f1a",
          borderBottom: "1px solid #1e1e2e",
          flexShrink: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Database size={16} style={{ color: "#3B82F6" }} />
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: -0.3 }}>Dodge AI</span>
          <span style={{ fontSize: 11, color: "#555" }}>SAP O2C Context Graph</span>
          {focalNodeId && (
            <button
              onClick={() => {
                useGraphStore.getState().resetGraph();
                loadInitialGraph();
              }}
              style={{
                fontSize: 11,
                padding: "3px 10px",
                background: "#1e1e30",
                border: "1px solid #333",
                borderRadius: 6,
                color: "#aaa",
                cursor: "pointer",
              }}
            >
              ← Overview
            </button>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ position: "relative" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#121222",
                border: "1px solid #2c2c40",
                borderRadius: 8,
                padding: "6px 10px",
                width: 260,
              }}
            >
              <Search size={14} style={{ color: "#666", flexShrink: 0 }} />
              <input
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setShowSearch(true);
                }}
                onFocus={() => setShowSearch(true)}
                placeholder="Find a node by id, label, or property"
                style={{
                  width: "100%",
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "#ddd",
                  fontSize: 12,
                }}
              />
            </div>
            {showSearch && searchQuery.trim() && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  width: 360,
                  maxHeight: 320,
                  overflowY: "auto",
                  background: "#0f0f1a",
                  border: "1px solid #2b2b40",
                  borderRadius: 10,
                  boxShadow: "0 12px 28px rgba(0,0,0,0.35)",
                  zIndex: 80,
                }}
              >
                {searchResults.length === 0 ? (
                  <div style={{ padding: "12px 14px", fontSize: 12, color: "#666" }}>
                    No matching nodes
                  </div>
                ) : (
                  searchResults.map((result) => (
                    <button
                      key={result.id}
                      onClick={() => handleSearchSelect(result.id)}
                      style={{
                        display: "block",
                        width: "100%",
                        textAlign: "left",
                        padding: "12px 14px",
                        background: "transparent",
                        border: "none",
                        borderBottom: "1px solid #1d1d30",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#e5e5e5", marginBottom: 2 }}>
                        {result.label}
                      </div>
                      <div style={{ fontSize: 11, color: "#777", marginBottom: 4 }}>
                        {result.type} · {result.id}
                      </div>
                      <div style={{ fontSize: 11, color: "#4f8cff" }}>
                        Focus node + up to 10 connected nodes
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Data Ingestion Button */}
          <button
            onClick={() => setShowDataPanel(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              padding: "5px 12px",
              background: "#1e1e30",
              border: "1px solid #333",
              borderRadius: 6,
              color: "#aaa",
              cursor: "pointer",
            }}
          >
            <FolderOpen size={12} />
            Data
          </button>

          {/* Stats */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: "#555" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <GitBranch size={11} /> {totalNodes} nodes
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <GitBranch size={11} /> {totalEdges} edges
            </span>
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 16px", background: "rgba(127,29,29,0.2)", borderBottom: "1px solid #7f1d1d", color: "#fca5a5", fontSize: 11 }}>
          <AlertTriangle size={13} />
          {error}
        </div>
      )}

      {/* ─── Main Content ──────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Graph */}
        <div style={{ flex: 1, position: "relative" }}>
          {isLoading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", background: "#1a1a2e" }}>
              <div style={{ textAlign: "center" }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    border: "2px solid #3B82F6",
                    borderTopColor: "transparent",
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                    margin: "0 auto 12px",
                  }}
                />
                <p style={{ fontSize: 12, color: "#555" }}>Loading graph...</p>
              </div>
            </div>
          ) : nodes.length === 0 ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", background: "#1a1a2e" }}>
              <div style={{ textAlign: "center", maxWidth: 400 }}>
                <Database size={40} style={{ color: "#333", margin: "0 auto 16px" }} />
                <p style={{ fontSize: 14, color: "#555", marginBottom: 8 }}>No data loaded</p>
                <p style={{ fontSize: 12, color: "#444", marginBottom: 16 }}>
                  Click the "Data" button above to browse and ingest your JSONL data files.
                </p>
                <button
                  onClick={() => setShowDataPanel(true)}
                  style={{
                    padding: "10px 20px",
                    background: "#1d4ed8",
                    border: "none",
                    borderRadius: 8,
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Load Data
                </button>
              </div>
            </div>
          ) : (
            <Neo4jGraph
              externalData={graphData}
              onExpandNode={handleExpandNode}
              highlightedIds={highlightedNodeIds}
              focalNodeId={focalNodeId}
              canShowMore={focalNodeId ? Boolean(expansionState[focalNodeId]?.hasMore) : remainingNodes > 0}
              showMoreLabel={
                focalNodeId
                  ? `Show 10 more neighbors (${Math.max(
                      (expansionState[focalNodeId]?.totalNeighbors || 0) -
                        (expansionState[focalNodeId]?.shownNeighbors || 0),
                      0
                    )} remaining)`
                  : `Show 10 more overview nodes (${remainingNodes} remaining)`
              }
              onShowMore={handleShowMore}
            />
          )}
        </div>

        {/* Chat Panel */}
        <div style={{ width: 400, borderLeft: "1px solid #1e1e2e", flexShrink: 0 }}>
          <ChatPanel onHighlight={handleChatHighlight} />
        </div>
      </div>

      {/* ─── Data Ingestion Modal ───────────────────────────────────────────────── */}
      {showDataPanel && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={() => setShowDataPanel(false)}
        >
          <div
            style={{ width: 600, maxHeight: "80vh", overflowY: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ position: "relative" }}>
              <button
                onClick={() => setShowDataPanel(false)}
                style={{
                  position: "absolute",
                  top: 12,
                  right: 12,
                  background: "transparent",
                  border: "none",
                  color: "#666",
                  cursor: "pointer",
                  zIndex: 10,
                }}
              >
                <X size={18} />
              </button>
              <DataIngestionPanel onIngestComplete={() => { setShowDataPanel(false); handleIngestComplete(); }} />
            </div>
          </div>
        </div>
      )}

      {/* Spinner keyframes */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #0f0f1a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
      `}</style>
    </div>
  );
}

export default App;
