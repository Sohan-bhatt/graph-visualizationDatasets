import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import ForceGraph2d from "react-force-graph-2d";

// ─── Types ────────────────────────────────────────────────────────────────────

interface NodeData {
  id: string;
  type: string;
  label: string;
  color: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
  vx?: number;
  vy?: number;
  degree?: number;
  is_anomaly?: boolean;
}

interface EdgeData {
  source: string | NodeData;
  target: string | NodeData;
  relationship: string;
  properties?: Record<string, unknown>;
}

interface GraphData {
  nodes: NodeData[];
  links: EdgeData[];
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  nodeId: string | null;
}

// ─── Color Map ────────────────────────────────────────────────────────────────

const NODE_COLORS: Record<string, string> = {
  SalesOrder: "#3B82F6",
  DeliveryDoc: "#10B981",
  BillingDoc: "#F59E0B",
  JournalEntry: "#8B5CF6",
  Payment: "#22D3EE",
  Customer: "#EF4444",
  Product: "#6B7280",
  Plant: "#84CC16",
};

const BASE_NODE_RADIUS = 18;
const FOCAL_NODE_RADIUS = 26;

// ─── Sample Data ──────────────────────────────────────────────────────────────

const SAMPLE_DATA: GraphData = {
  nodes: [
    { id: "CUST_320000083", type: "Customer", label: "Cardenas Parker", color: NODE_COLORS.Customer, properties: { businessPartner: "320000083", fullName: "Cardenas, Parker and Avila", category: "Organization", grouping: "Y101" } },
    { id: "SO_740506", type: "SalesOrder", label: "SO 740506", color: NODE_COLORS.SalesOrder, properties: { salesOrder: "740506", totalNetAmount: "17108.25 INR", deliveryStatus: "Completed", creationDate: "2025-03-31" } },
    { id: "DEL_80737721", type: "DeliveryDoc", label: "DEL 80737721", color: NODE_COLORS.DeliveryDoc, properties: { deliveryDocument: "80737721", shippingPoint: "1920", goodsMovementStatus: "Not Processed", pickingStatus: "Completed" } },
    { id: "BILL_90504248", type: "BillingDoc", label: "BILL 90504248", color: NODE_COLORS.BillingDoc, properties: { billingDocument: "90504248", type: "F2 Invoice", amount: "216.1 INR", isCancelled: false, accountingDocument: "9400000249" } },
    { id: "PROD_S8907367001003", type: "Product", label: "BEARDOIL 30ML", color: NODE_COLORS.Product, properties: { product: "S8907367001003", description: "BEARDOIL 30ML ALMOND+THYME", type: "ZFS1", weight: "0.025 KG" } },
  ],
  links: [
    { source: "CUST_320000083", target: "SO_740506", relationship: "PLACED" },
    { source: "SO_740506", target: "DEL_80737721", relationship: "FULFILLED_BY" },
    { source: "DEL_80737721", target: "BILL_90504248", relationship: "BILLED_IN" },
    { source: "SO_740506", target: "PROD_S8907367001003", relationship: "CONTAINS_ITEM" },
  ],
};

// ─── Utility ──────────────────────────────────────────────────────────────────

function getNodeId(node: string | NodeData): string {
  return typeof node === "string" ? node : node.id;
}

function truncateText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let truncated = text;
  while (ctx.measureText(truncated + "...").width > maxWidth && truncated.length > 0) {
    truncated = truncated.slice(0, -1);
  }
  return truncated + "...";
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface Neo4jGraphProps {
  externalData?: GraphData;
  onExpandNode?: (nodeId: string) => void;
  highlightedIds?: Set<string>;
  focalNodeId?: string | null;
  canShowMore?: boolean;
  showMoreLabel?: string;
  onShowMore?: () => void;
}

export default function Neo4jGraph({
  externalData,
  onExpandNode,
  highlightedIds,
  focalNodeId = null,
  canShowMore = false,
  showMoreLabel = "Show more",
  onShowMore,
}: Neo4jGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });

  // State
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeIdx, setHoveredEdgeIdx] = useState<number | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, nodeId: null });
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState<Set<string>>(new Set());

  // Use external data or sample data
  const data = useMemo(() => {
    const raw = externalData || SAMPLE_DATA;
    return {
      nodes: raw.nodes.map((n) => ({
        ...n,
        color: NODE_COLORS[n.type] || n.color || "#6B7280",
        degree: n.degree || 0,
      })),
      links: raw.links,
    };
  }, [externalData]);

  // Computed
  const selectedNode = useMemo(
    () => data.nodes.find((n) => n.id === selectedNodeId) || null,
    [data.nodes, selectedNodeId]
  );

  useEffect(() => {
    if (focalNodeId && data.nodes.some((node) => node.id === focalNodeId)) {
      setSelectedNodeId(focalNodeId);
    }
  }, [data.nodes, focalNodeId]);

  const neighborsOfSelected = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const neighbors = new Set<string>();
    neighbors.add(selectedNodeId);
    for (const link of data.links) {
      const src = getNodeId(link.source);
      const tgt = getNodeId(link.target);
      if (src === selectedNodeId) neighbors.add(tgt);
      if (tgt === selectedNodeId) neighbors.add(src);
    }
    return neighbors;
  }, [data.links, selectedNodeId]);

  const connectedEdgesOfSelected = useMemo(() => {
    if (!selectedNodeId) return new Set<number>();
    const edges = new Set<number>();
    data.links.forEach((link, idx) => {
      const src = getNodeId(link.source);
      const tgt = getNodeId(link.target);
      if (src === selectedNodeId || tgt === selectedNodeId) {
        edges.add(idx);
      }
    });
    return edges;
  }, [data.links, selectedNodeId]);

  // Resize
  useEffect(() => {
    const update = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // Search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchMatches(new Set());
      return;
    }
    const q = searchQuery.toLowerCase();
    const matches = new Set<string>();
    for (const node of data.nodes) {
      const label = (node.label || "").toLowerCase();
      const id = node.id.toLowerCase();
      const type = node.type.toLowerCase();
      const propsStr = Object.values(node.properties || {})
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      if (label.includes(q) || id.includes(q) || type.includes(q) || propsStr.includes(q)) {
        matches.add(node.id);
      }
    }
    setSearchMatches(matches);
  }, [searchQuery, data.nodes]);

  // Close context menu on click elsewhere
  useEffect(() => {
    const handler = () => setContextMenu((m) => ({ ...m, visible: false }));
    window.addEventListener("click", handler);
    return () => window.removeEventListener("click", handler);
  }, []);

  // Fit to screen once on load
  useEffect(() => {
    if (graphRef.current && data.nodes.length > 0) {
      const timer = setTimeout(() => {
        graphRef.current?.zoomToFit(400, 60);
        const minReadableZoom = focalNodeId ? 1.2 : 0.8;
        const currentZoom = graphRef.current?.zoom?.() || 1;
        if (currentZoom < minReadableZoom) {
          graphRef.current?.zoom(minReadableZoom, 350);
        }
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [data.nodes.length, focalNodeId]);

  useEffect(() => {
    if (!graphRef.current || !focalNodeId) return;
    const focal = data.nodes.find((node) => node.id === focalNodeId);
    if (!focal || focal.x === undefined || focal.y === undefined) return;

    const timer = setTimeout(() => {
      graphRef.current?.centerAt(focal.x, focal.y, 450);
      graphRef.current?.zoom(1.65, 450);
    }, 500);

    return () => clearTimeout(timer);
  }, [data.nodes, focalNodeId]);

  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || data.nodes.length === 0 || !fg.d3Force) return;

    fg.d3Force("charge")?.strength(focalNodeId ? -1500 : -1100);
    fg.d3Force("link")?.distance((link: any) => {
      const srcId = getNodeId(link.source);
      const tgtId = getNodeId(link.target);
      if (focalNodeId && (srcId === focalNodeId || tgtId === focalNodeId)) {
        return 240;
      }
      return focalNodeId ? 180 : 150;
    });
    fg.d3Force("orbit", null);
    if (focalNodeId) {
      fg.d3Force("orbit", (alpha: number) => {
        const focal = data.nodes.find((node) => node.id === focalNodeId);
        if (!focal || focal.x === undefined || focal.y === undefined) return;

        const neighbors = data.nodes.filter((node) => node.id !== focalNodeId);
        const step = (Math.PI * 2) / Math.max(neighbors.length, 1);
        neighbors.forEach((node, index) => {
          const angle = index * step;
          const targetX = focal.x! + Math.cos(angle) * 220;
          const targetY = focal.y! + Math.sin(angle) * 220;
          node.vx = (node.vx || 0) + (targetX - (node.x || 0)) * alpha * 0.12;
          node.vy = (node.vy || 0) + (targetY - (node.y || 0)) * alpha * 0.12;
        });
      });
    }
    fg.d3ReheatSimulation?.();
  }, [data, focalNodeId]);

  // ─── Canvas Renderers ───────────────────────────────────────────────────────

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as NodeData;
      const isFocal = n.id === focalNodeId;
      const radius = (isFocal ? FOCAL_NODE_RADIUS : BASE_NODE_RADIUS) / globalScale;
      const isSelected = n.id === selectedNodeId;
      const isHighlighted = highlightedIds?.has(n.id) || false;
      const isNeighbor = neighborsOfSelected.has(n.id);
      const isSearchMatch = searchMatches.has(n.id);
      const isHovered = n.id === hoveredNodeId;

      // Determine opacity
      let opacity = 1;
      if (selectedNodeId && !isNeighbor) {
        opacity = 0.1;
      }
      if (isSearchMatch && searchQuery) {
        opacity = 1;
      }

      ctx.globalAlpha = opacity;

      // Outer ring for selected
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(n.x!, n.y!, radius + 3 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 3 / globalScale;
        ctx.stroke();
      }

      // Ring for highlighted (from chat)
      if (isHighlighted && !isSelected) {
        ctx.beginPath();
        ctx.arc(n.x!, n.y!, radius + 2 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = "#FBBF24";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      // Ring for search match
      if (isSearchMatch && !isSelected && !isHighlighted) {
        ctx.beginPath();
        ctx.arc(n.x!, n.y!, radius + 2 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = "#60A5FA";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      // Node fill
      const fillColor = isHovered ? lightenColor(n.color, 25) : n.color;
      ctx.beginPath();
      ctx.arc(n.x!, n.y!, radius, 0, 2 * Math.PI);
      ctx.fillStyle = fillColor;
      ctx.fill();

      if (isFocal) {
        ctx.beginPath();
        ctx.arc(n.x!, n.y!, radius + 8 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = "rgba(255,255,255,0.55)";
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      const shortLabel = n.label
        .replace(/^SalesOrder\s+/i, "SO ")
        .replace(/^DeliveryDoc\s+/i, "DEL ")
        .replace(/^BillingDoc\s+/i, "BILL ")
        .replace(/^JournalEntry\s+/i, "JE ")
        .replace(/^Customer\s+/i, "")
        .replace(/^Product\s+/i, "");

      // Keep labels outside the circles for readability
      if (globalScale > 0.22 || isFocal || isHovered || isSelected) {
        const labelFontSize = Math.max(8, 10 / globalScale);
        ctx.font = `600 ${labelFontSize}px "Inter", "Segoe UI", sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const maxTextWidth = (isFocal ? 150 : 110) / globalScale;
        const displayLabel = truncateText(ctx, shortLabel, maxTextWidth);
        const textWidth = ctx.measureText(displayLabel).width;
        const padX = 8 / globalScale;
        const pillHeight = 18 / globalScale;
        const pillY = n.y! + radius + 14 / globalScale;
        ctx.fillStyle = "rgba(10,10,20,0.82)";
        ctx.beginPath();
        ctx.roundRect(
          n.x! - textWidth / 2 - padX,
          pillY - pillHeight / 2,
          textWidth + padX * 2,
          pillHeight,
          8 / globalScale
        );
        ctx.fill();

        ctx.fillStyle = "#F8FAFC";
        ctx.fillText(displayLabel, n.x!, pillY);

        if (isFocal || isHovered || isSelected) {
          const metaFontSize = Math.max(7, 8.5 / globalScale);
          ctx.font = `${metaFontSize}px "Inter", sans-serif`;
          ctx.fillStyle = "rgba(255,255,255,0.6)";
          ctx.fillText(
            isFocal ? `${n.type} · focus` : n.type,
            n.x!,
            pillY + 13 / globalScale
          );
        }
      }

      ctx.globalAlpha = 1;
    },
    [selectedNodeId, hoveredNodeId, neighborsOfSelected, highlightedIds, searchMatches, searchQuery, focalNodeId]
  );

  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const idx = data.links.indexOf(link);
      const edgeData = link as EdgeData;
      const src = link.source as NodeData;
      const tgt = link.target as NodeData;

      if (!src.x || !src.y || !tgt.x || !tgt.y) return;

      const isConnectedToSelected = connectedEdgesOfSelected.has(idx);
      const isHoveredEdge = hoveredEdgeIdx === idx;
      const isFocalEdge = focalNodeId
        ? getNodeId(edgeData.source) === focalNodeId || getNodeId(edgeData.target) === focalNodeId
        : false;

      let opacity = 1;
      if (selectedNodeId && !isConnectedToSelected) {
        opacity = 0.06;
      }
      ctx.globalAlpha = opacity;

      // Line color
      const lineColor = isHoveredEdge
        ? "#F8FAFC"
        : isFocalEdge
          ? "rgba(148,163,184,0.85)"
          : isConnectedToSelected
            ? "rgba(148,163,184,0.6)"
            : "rgba(100,116,139,0.22)";
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = (isHoveredEdge ? 2.2 : isFocalEdge ? 1.8 : 1.1) / globalScale;

      // Direction: compute arrow position
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist === 0) return;

      const ux = dx / dist;
      const uy = dy / dist;

      // Shorten line to not overlap node circles
      const srcR = (getNodeId(edgeData.source) === focalNodeId ? FOCAL_NODE_RADIUS : BASE_NODE_RADIUS) / globalScale;
      const tgtR = (getNodeId(edgeData.target) === focalNodeId ? FOCAL_NODE_RADIUS : BASE_NODE_RADIUS) / globalScale;
      const x1 = src.x + ux * srcR;
      const y1 = src.y + uy * srcR;
      const x2 = tgt.x - ux * (tgtR + 6 / globalScale);
      const y2 = tgt.y - uy * (tgtR + 6 / globalScale);

      // Draw line
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      // Arrowhead
      const arrowSize = 7 / globalScale;
      const arrowX = x2;
      const arrowY = y2;
      ctx.beginPath();
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(
        arrowX - arrowSize * ux + (arrowSize * 0.4) * uy,
        arrowY - arrowSize * uy - (arrowSize * 0.4) * ux
      );
      ctx.lineTo(
        arrowX - arrowSize * ux - (arrowSize * 0.4) * uy,
        arrowY - arrowSize * uy + (arrowSize * 0.4) * ux
      );
      ctx.closePath();
      ctx.fillStyle = lineColor;
      ctx.fill();

      // Edge label (centered on line)
      if (isHoveredEdge && edgeData.relationship) {
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;

        const labelFontSize = Math.max(8, 10 / globalScale);
        ctx.font = `${labelFontSize}px "Inter", sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        // Background pill for readability
        const labelText = edgeData.relationship;
        const textWidth = ctx.measureText(labelText).width;
        const pad = 3 / globalScale;
        ctx.fillStyle = "rgba(12,18,28,0.96)";
        ctx.beginPath();
        ctx.roundRect(
          midX - textWidth / 2 - pad,
          midY - labelFontSize / 2 - pad,
          textWidth + pad * 2,
          labelFontSize + pad * 2,
          3 / globalScale
        );
        ctx.fill();

        ctx.fillStyle = "#FFFFFF";
        ctx.fillText(labelText, midX, midY);
      }

      ctx.globalAlpha = 1;
    },
    [data.links, connectedEdgesOfSelected, selectedNodeId, hoveredEdgeIdx, focalNodeId]
  );

  // ─── Event Handlers ─────────────────────────────────────────────────────────

  const handleNodeClick = useCallback(
    (node: any) => {
      const n = node as NodeData;
      setSelectedNodeId((prev) => (prev === n.id ? null : n.id));
      setContextMenu({ visible: false, x: 0, y: 0, nodeId: null });
    },
    []
  );

  const handleBackgroundClick = useCallback(() => {
    setSelectedNodeId(null);
    setContextMenu({ visible: false, x: 0, y: 0, nodeId: null });
  }, []);

  const handleNodeRightClick = useCallback((node: any, event: MouseEvent) => {
    event.preventDefault();
    const n = node as NodeData;
    setContextMenu({
      visible: true,
      x: event.clientX,
      y: event.clientY,
      nodeId: n.id,
    });
  }, []);

  const handleNodeHover = useCallback((node: any | null) => {
    setHoveredNodeId(node ? (node as NodeData).id : null);
  }, []);

  const handleLinkHover = useCallback((link: any | null) => {
    if (link) {
      const idx = SAMPLE_DATA.links.indexOf(link);
      // For external data we need to find it differently
      setHoveredEdgeIdx(typeof link.__index === "number" ? link.__index : null);
    } else {
      setHoveredEdgeIdx(null);
    }
  }, []);

  // ─── Helpers ────────────────────────────────────────────────────────────────

  function lightenColor(hex: string, percent: number): string {
    const num = parseInt(hex.replace("#", ""), 16);
    const r = Math.min(255, (num >> 16) + percent);
    const g = Math.min(255, ((num >> 8) & 0x00ff) + percent);
    const b = Math.min(255, (num & 0x0000ff) + percent);
    return `rgb(${r},${g},${b})`;
  }

  const handleZoomIn = () => {
    if (graphRef.current) {
      const current = graphRef.current.zoom();
      graphRef.current.zoom(Math.min(current * 1.4, 8), 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const current = graphRef.current.zoom();
      graphRef.current.zoom(Math.max(current / 1.4, 0.1), 300);
    }
  };

  const handleFit = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 60);
    }
  };

  const handleCopyId = useCallback(() => {
    if (contextMenu.nodeId) {
      navigator.clipboard.writeText(contextMenu.nodeId);
    }
    setContextMenu({ visible: false, x: 0, y: 0, nodeId: null });
  }, [contextMenu.nodeId]);

  const handleContextExpand = useCallback(() => {
    if (contextMenu.nodeId && onExpandNode) {
      onExpandNode(contextMenu.nodeId);
    }
    setContextMenu({ visible: false, x: 0, y: 0, nodeId: null });
  }, [contextMenu.nodeId, onExpandNode]);

  const handleContextHide = useCallback(() => {
    // For now just deselect
    setContextMenu({ visible: false, x: 0, y: 0, nodeId: null });
  }, []);

  // ─── Render ─────────────────────────────────────────────────────────────────

  // Augment links with index for hover tracking
  const augmentedData = useMemo(() => {
    return {
      nodes: data.nodes,
      links: data.links.map((l, i) => ({ ...l, __index: i })),
    };
  }, [data]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        background: "#1a1a2e",
        overflow: "hidden",
        fontFamily: '"Inter", "Segoe UI", system-ui, sans-serif',
      }}
    >
      {/* ─── Controls (top-left) ──────────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 30,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {/* Search */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            background: "#0f0f1a",
            border: "1px solid #333",
            borderRadius: 8,
            padding: "6px 12px",
            width: 240,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2" style={{ marginRight: 8, flexShrink: 0 }}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes..."
            style={{
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#ddd",
              fontSize: 12,
              width: "100%",
            }}
          />
          {searchMatches.size > 0 && (
            <span style={{ color: "#60A5FA", fontSize: 11, flexShrink: 0, marginLeft: 4 }}>
              {searchMatches.size}
            </span>
          )}
        </div>

        {/* Zoom buttons */}
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={handleZoomIn} style={controlBtnStyle} title="Zoom in">+</button>
          <button onClick={handleZoomOut} style={controlBtnStyle} title="Zoom out">−</button>
          <button onClick={handleFit} style={controlBtnStyle} title="Fit to screen">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="2">
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* ─── Legend (bottom-left) ─────────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          bottom: 16,
          left: 16,
          zIndex: 30,
          background: "rgba(15,15,26,0.92)",
          border: "1px solid #333",
          borderRadius: 8,
          padding: "10px 14px",
        }}
      >
        <div style={{ fontSize: 10, color: "#888", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
          Node Types
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: color,
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 11, color: "#bbb" }}>{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Node count (top-right) ───────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: 16,
          right: selectedNode ? 300 : 16,
          zIndex: 30,
          background: "rgba(15,15,26,0.85)",
          border: "1px solid #333",
          borderRadius: 8,
          padding: "6px 12px",
          fontSize: 11,
          color: "#888",
          transition: "right 0.3s ease",
        }}
      >
        {data.nodes.length} nodes &middot; {data.links.length} edges
      </div>

      <div
        style={{
          position: "absolute",
          top: 56,
          right: selectedNode ? 300 : 16,
          zIndex: 30,
          background: "rgba(15,15,26,0.85)",
          border: "1px solid #333",
          borderRadius: 8,
          padding: "6px 12px",
          fontSize: 11,
          color: "#888",
          transition: "right 0.3s ease",
        }}
      >
        {focalNodeId
          ? "Focal view: 1 node + 10 direct connections per page"
          : "Overview: top 10 most connected nodes"}
      </div>

      {/* ─── Force Graph ──────────────────────────────────────────────────────── */}
      <ForceGraph2d
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={augmentedData}
        backgroundColor="#1a1a2e"
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const isFocal = node.id === focalNodeId;
          const hitRadius = isFocal ? 30 : 24;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, hitRadius, 0, 2 * Math.PI);
          ctx.fill();
        }}
        linkCanvasObject={linkCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        linkCanvasObjectMode={() => "replace"}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleBackgroundClick}
        onNodeRightClick={handleNodeRightClick}
        onNodeHover={handleNodeHover}
        onLinkHover={handleLinkHover}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        minZoom={0.1}
        maxZoom={8}
        warmupTicks={80}
        cooldownTicks={0}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
      />

      {/* ─── Edge Hover Tooltip ───────────────────────────────────────────────── */}
      {hoveredEdgeIdx !== null && hoveredEdgeIdx >= 0 && hoveredEdgeIdx < data.links.length && (
        <div
          style={{
            position: "absolute",
            bottom: 50,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#0f0f1a",
            border: "1px solid #444",
            borderRadius: 6,
            padding: "4px 12px",
            fontSize: 12,
            color: "#fff",
            zIndex: 40,
            pointerEvents: "none",
          }}
        >
          {data.links[hoveredEdgeIdx]?.relationship}
        </div>
      )}

      {canShowMore && onShowMore && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            bottom: 20,
            transform: "translateX(-50%)",
            zIndex: 35,
          }}
        >
          <button
            onClick={onShowMore}
            style={{
              padding: "10px 16px",
              background: "#2563eb",
              border: "1px solid #3b82f6",
              borderRadius: 999,
              color: "#fff",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 10px 24px rgba(37,99,235,0.28)",
            }}
          >
            {showMoreLabel}
          </button>
        </div>
      )}

      {/* ─── Context Menu ─────────────────────────────────────────────────────── */}
      {contextMenu.visible && (
        <div
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            background: "#0f0f1a",
            border: "1px solid #444",
            borderRadius: 8,
            padding: 4,
            zIndex: 100,
            minWidth: 160,
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {[
            { label: "Expand Neighbors", action: handleContextExpand },
            { label: "Hide Node", action: handleContextHide },
            { label: "Copy ID", action: handleCopyId },
          ].map((item) => (
            <button
              key={item.label}
              onClick={item.action}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                background: "transparent",
                border: "none",
                color: "#ddd",
                padding: "8px 12px",
                fontSize: 12,
                borderRadius: 4,
                cursor: "pointer",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#1e1e30")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* ─── Detail Panel (right side) ────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          right: selectedNode ? 0 : -300,
          width: 280,
          height: "100%",
          background: "#0f0f1a",
          borderLeft: "1px solid #333",
          zIndex: 25,
          transition: "right 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {selectedNode && (
          <>
            {/* Header */}
            <div
              style={{
                padding: "16px 16px 12px",
                borderBottom: "1px solid #222",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: selectedNode.color,
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    color: selectedNode.color,
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    fontWeight: 600,
                    background: `${selectedNode.color}22`,
                    padding: "2px 8px",
                    borderRadius: 10,
                  }}
                >
                  {selectedNode.type}
                </span>
              </div>
              <button
                onClick={() => setSelectedNodeId(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#666",
                  cursor: "pointer",
                  fontSize: 18,
                  lineHeight: 1,
                  padding: 4,
                }}
              >
                ×
              </button>
            </div>

            {/* Node name */}
            <div style={{ padding: "12px 16px 8px" }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", marginBottom: 4 }}>
                {selectedNode.label}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "#666",
                  fontFamily: '"Fira Code", "Cascadia Code", "Consolas", monospace',
                }}
              >
                {selectedNode.id}
              </div>
            </div>

            {/* Properties */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "8px 16px 16px",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  color: "#555",
                  textTransform: "uppercase",
                  letterSpacing: 1,
                  marginBottom: 8,
                }}
              >
                Properties
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                {Object.entries(selectedNode.properties).map(([key, value]) => (
                  <div
                    key={key}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      padding: "7px 0",
                      borderBottom: "1px solid #1a1a2a",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        color: "#888",
                        fontFamily: '"Fira Code", monospace',
                        flexShrink: 0,
                        marginRight: 12,
                      }}
                    >
                      {key}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        color: "#ddd",
                        textAlign: "right",
                        wordBreak: "break-all",
                        fontFamily: '"Fira Code", monospace',
                      }}
                    >
                      {value === null || value === undefined || value === ""
                        ? "—"
                        : String(value)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Connection info */}
              <div style={{ marginTop: 16 }}>
                <div
                  style={{
                    fontSize: 10,
                    color: "#555",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    marginBottom: 8,
                  }}
                >
                  Connections
                </div>
                <div style={{ fontSize: 12, color: "#aaa" }}>
                  {neighborsOfSelected.size - 1} direct neighbor{neighborsOfSelected.size - 1 !== 1 ? "s" : ""}
                </div>
              </div>
            </div>

            {/* Expand button */}
            <div style={{ padding: "12px 16px", borderTop: "1px solid #222" }}>
              <button
                onClick={() => {
                  if (selectedNode.id === focalNodeId) {
                    onShowMore?.();
                    return;
                  }
                  if (onExpandNode) onExpandNode(selectedNode.id);
                }}
                style={{
                  width: "100%",
                  padding: "10px",
                  background: selectedNode.color,
                  border: "none",
                  borderRadius: 6,
                  color: "#fff",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: selectedNode.id === focalNodeId && !canShowMore ? "default" : "pointer",
                  transition: "opacity 0.2s",
                  opacity: selectedNode.id === focalNodeId && !canShowMore ? 0.65 : 1,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = selectedNode.id === focalNodeId && !canShowMore ? "0.65" : "1")}
                disabled={selectedNode.id === focalNodeId && !canShowMore}
              >
                {selectedNode.id === focalNodeId
                  ? canShowMore
                    ? "Show More Neighbors"
                    : "All Visible Neighbors Loaded"
                  : "Expand Neighbors"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const controlBtnStyle: React.CSSProperties = {
  width: 32,
  height: 32,
  background: "#0f0f1a",
  border: "1px solid #333",
  borderRadius: 6,
  color: "#aaa",
  fontSize: 16,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  transition: "background 0.15s",
};

export { NODE_COLORS, SAMPLE_DATA };
export type { NodeData, EdgeData, GraphData, Neo4jGraphProps };
