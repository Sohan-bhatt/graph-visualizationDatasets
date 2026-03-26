import { X, ChevronRight, AlertTriangle, ChevronDown } from "lucide-react";
import type { GraphNode } from "../types/graph";
import { NODE_COLORS } from "../utils/graphColors";

interface NodeInspectorProps {
  node: GraphNode;
  expansionState?: { totalNeighbors: number; shownNeighbors: number; hasMore: boolean };
  onClose: () => void;
  onExpand: (nodeId: string) => void;
  onFocus: (nodeId: string) => void;
}

export default function NodeInspector({ node, expansionState, onClose, onExpand, onFocus }: NodeInspectorProps) {
  const color = NODE_COLORS[node.type] || "#9CA3AF";
  const properties = node.metadata?.properties || {};

  return (
    <div className="absolute left-0 top-0 bottom-0 w-80 bg-gray-900/95 border-r border-gray-700 z-20 overflow-y-auto backdrop-blur-sm">
      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm border-b border-gray-700 p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
          <span className="font-semibold text-sm text-gray-100">{node.type}</span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-700 rounded transition-colors">
          <X size={16} className="text-gray-400" />
        </button>
      </div>

      <div className="p-4">
        <h3 className="text-lg font-bold text-gray-100 mb-1">{node.label}</h3>
        <p className="text-xs text-gray-500 mb-4">ID: {node.id}</p>

        {node.is_anomaly && (
          <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 rounded-lg px-3 py-2 mb-4">
            <AlertTriangle size={14} className="text-red-400" />
            <span className="text-xs text-red-300">Part of an incomplete flow</span>
          </div>
        )}

        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>Connections: {node.degree}</span>
            {expansionState && (
              <span>{expansionState.shownNeighbors} / {expansionState.totalNeighbors} shown</span>
            )}
          </div>
          {expansionState && (
            <div className="w-full bg-gray-800 rounded-full h-1.5 mb-2">
              <div
                className="bg-blue-500 h-1.5 rounded-full transition-all"
                style={{ width: `${Math.min(100, (expansionState.shownNeighbors / Math.max(1, expansionState.totalNeighbors)) * 100)}%` }}
              />
            </div>
          )}
        </div>

        <div className="mb-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Properties</h4>
          <div className="space-y-1">
            {Object.entries(properties).map(([key, value]) => (
              <div key={key} className="flex justify-between items-start text-xs py-1.5 border-b border-gray-800">
                <span className="text-gray-400 font-medium shrink-0 mr-2">{key}</span>
                <span className="text-gray-200 text-right break-all">
                  {value === null || value === "" ? (
                    <span className="text-gray-600 italic">empty</span>
                  ) : (
                    String(value)
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <button
            onClick={() => onFocus(node.id)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Focus on This Node
          </button>

          <button
            onClick={() => onExpand(node.id)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {expansionState && expansionState.hasMore ? (
              <>
                <ChevronDown size={14} />
                Show More Neighbors ({expansionState.totalNeighbors - expansionState.shownNeighbors} remaining)
              </>
            ) : (
              <>
                <ChevronRight size={14} />
                Expand Neighbors
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
