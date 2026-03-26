import { useState, useRef, useEffect, useCallback } from "react";
import ForceGraph2d from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../types/graph";
import { getNodeColor, getNodeSize, NODE_COLORS } from "../utils/graphColors";

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedNodeIds: Set<string>;
  focalNodeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeDoubleClick: (nodeId: string) => void;
  onShowMore: (nodeId: string) => void;
  expansionState: Record<string, { totalNeighbors: number; shownNeighbors: number; hasMore: boolean }>;
}

export default function GraphCanvas({
  nodes,
  edges,
  highlightedNodeIds,
  focalNodeId,
  onNodeClick,
  onNodeDoubleClick,
  onShowMore,
  expansionState,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Convert to force-graph format
  const graphData = {
    nodes: nodes.map((n) => {
      const isHighlighted = highlightedNodeIds.has(n.id);
      const isFocal = n.id === focalNodeId;
      return {
        id: n.id,
        name: n.label,
        type: n.type,
        degree: n.degree,
        is_anomaly: n.is_anomaly,
        is_focal: isFocal,
        is_highlighted: isHighlighted,
        color: getNodeColor(n.type, n.is_anomaly, isHighlighted),
        val: isFocal ? 12 : getNodeSize(n.degree),
      };
    }),
    links: edges.map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.relationship,
    })),
  };

  const handleNodeClick = useCallback(
    (node: any) => {
      const original = nodes.find((n) => n.id === node.id);
      if (original) onNodeClick(original);
    },
    [nodes, onNodeClick]
  );

  // Cluster nodes by type using force simulation groups
  useEffect(() => {
    if (graphRef.current) {
      // Apply clustering force - group nodes of same type together
      const typePositions: Record<string, { x: number; y: number }> = {
        Customer: { x: -200, y: -100 },
        SalesOrder: { x: 0, y: -150 },
        Product: { x: 200, y: -100 },
        Plant: { x: 250, y: 50 },
        DeliveryDoc: { x: -150, y: 100 },
        BillingDoc: { x: 0, y: 150 },
        JournalEntry: { x: 150, y: 100 },
        Payment: { x: 0, y: 250 },
      };

      // d3-force clustering via node positioning hints
      const fg = graphRef.current;
      if (fg.d3Force) {
        fg.d3Force("cluster", (alpha: number) => {
          graphData.nodes.forEach((node: any) => {
            const pos = typePositions[node.type] || { x: 0, y: 0 };
            node.vx = (node.vx || 0) + (pos.x - (node.x || 0)) * alpha * 0.1;
            node.vy = (node.vy || 0) + (pos.y - (node.y || 0)) * alpha * 0.1;
          });
        });
      }
    }
  }, [nodes.length]);

  return (
    <div ref={containerRef} className="relative w-full h-full bg-gray-950">
      <ForceGraph2d
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
          const size = node.val || 4;
          const color = node.color || "#9CA3AF";

          // Pulsing ring for highlighted nodes
          if (node.is_highlighted) {
            const pulseSize = size + 4 + Math.sin(Date.now() / 300) * 2;
            ctx.beginPath();
            ctx.arc(node.x, node.y, pulseSize, 0, 2 * Math.PI);
            ctx.fillStyle = "rgba(251, 191, 36, 0.25)";
            ctx.fill();
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 2, 0, 2 * Math.PI);
            ctx.strokeStyle = "#FBBF24";
            ctx.lineWidth = 2 / globalScale;
            ctx.stroke();
          }

          // Focal node ring
          if (node.is_focal) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 5, 0, 2 * Math.PI);
            ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
            ctx.fill();
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 3, 0, 2 * Math.PI);
            ctx.strokeStyle = "#3B82F6";
            ctx.lineWidth = 2 / globalScale;
            ctx.stroke();
          }

          // Node circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();

          // Label
          const label = node.name || node.id;
          const fontSize = Math.max(8, 10 / globalScale);
          ctx.font = `${fontSize}px Inter, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = node.is_focal ? "#FFFFFF" : "#D1D5DB";
          ctx.fillText(label, node.x, node.y + size + 2);
        }}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkColor={() => "rgba(107, 114, 128, 0.3)"}
        linkWidth={1}
        onNodeClick={handleNodeClick}
        cooldownTicks={100}
        onEngineStop={() => graphRef.current?.zoomToFit(400)}
      />

      {/* Zoom Controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1">
        <button
          onClick={() => graphRef.current?.zoom((graphRef.current?.zoom?.() || 1) * 1.3)}
          className="w-8 h-8 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg flex items-center justify-center text-lg font-bold border border-gray-700"
        >
          +
        </button>
        <button
          onClick={() => graphRef.current?.zoom((graphRef.current?.zoom?.() || 1) / 1.3)}
          className="w-8 h-8 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg flex items-center justify-center text-lg font-bold border border-gray-700"
        >
          -
        </button>
        <button
          onClick={() => graphRef.current?.zoomToFit(400)}
          className="w-8 h-8 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg flex items-center justify-center text-xs border border-gray-700"
          title="Fit all nodes"
        >
          &#8634;
        </button>
      </div>

      {/* Show More — Global */}
      {focalNodeId === null && expansionState["__global__"]?.hasMore && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2">
          <button
            onClick={() => onShowMore("__global__")}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg shadow-lg flex items-center gap-2"
          >
            Show More ({expansionState["__global__"].totalNeighbors - expansionState["__global__"].shownNeighbors} remaining)
          </button>
        </div>
      )}

      {/* Show More — Focal node neighbors */}
      {focalNodeId && expansionState[focalNodeId]?.hasMore && (
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2">
          <button
            onClick={() => onShowMore(focalNodeId)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg shadow-lg flex items-center gap-2"
          >
            Show More ({expansionState[focalNodeId].totalNeighbors - expansionState[focalNodeId].shownNeighbors} of {expansionState[focalNodeId].totalNeighbors} remaining)
          </button>
        </div>
      )}

      {/* Legend */}
      <div className="absolute top-3 right-3 bg-gray-900/90 border border-gray-700 rounded-lg p-3 backdrop-blur-sm">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Legend
        </h4>
        <div className="space-y-1">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="text-xs text-gray-300">{type}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 border-t border-gray-700 space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-blue-500 ring-2 ring-blue-400" />
            <span className="text-xs text-gray-400">Focal node</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-yellow-500 ring-2 ring-yellow-400" />
            <span className="text-xs text-gray-400">Highlighted</span>
          </div>
        </div>
      </div>

      {/* Node count */}
      <div className="absolute top-3 left-3 bg-gray-900/80 border border-gray-700 rounded-lg px-3 py-1.5 backdrop-blur-sm">
        <span className="text-xs text-gray-400">Showing {nodes.length} nodes</span>
      </div>
    </div>
  );
}
