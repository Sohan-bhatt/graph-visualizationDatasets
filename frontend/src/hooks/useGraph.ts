import { create } from "zustand";
import type { GraphNode, GraphEdge } from "../types/graph";
import { fetchInitialGraph, expandNode, fetchFocalSubgraph } from "../api/client";

const INITIAL_GRAPH_LIMIT = 10;
const NEIGHBOR_PAGE_SIZE = 10;

interface NodeExpansionState {
  totalNeighbors: number;
  shownNeighbors: number;
  offset: number;
  hasMore: boolean;
}

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  visibleNodeIds: Set<string>;
  highlightedNodeIds: Set<string>;
  selectedNode: GraphNode | null;
  focalNodeId: string | null;
  renderMode: "push" | "pull";
  isLoading: boolean;
  totalNodes: number;
  totalEdges: number;
  remainingNodes: number;
  overviewLimit: number;
  error: string | null;

  // Track expansion state per node
  expansionState: Record<string, NodeExpansionState>;

  loadInitialGraph: () => Promise<void>;
  loadMoreOverview: () => Promise<void>;
  expandNodeNeighbors: (nodeId: string) => Promise<void>;
  loadFocalSubgraph: (nodeId: string) => Promise<void>;
  highlightNodes: (ids: string[]) => void;
  selectNode: (node: GraphNode | null) => void;
  clearHighlights: () => void;
  resetGraph: () => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: [],
  edges: [],
  visibleNodeIds: new Set(),
  highlightedNodeIds: new Set(),
  selectedNode: null,
  focalNodeId: null,
  renderMode: "pull",
  isLoading: false,
  totalNodes: 0,
  totalEdges: 0,
  remainingNodes: 0,
  overviewLimit: INITIAL_GRAPH_LIMIT,
  error: null,
  expansionState: {},

  loadInitialGraph: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await fetchInitialGraph(INITIAL_GRAPH_LIMIT);
      const visibleIds = new Set(data.nodes.map((n) => n.id));

      set({
        nodes: data.nodes,
        edges: data.edges,
        visibleNodeIds: visibleIds,
        renderMode: data.render_mode,
        totalNodes: data.total_nodes,
        totalEdges: data.total_edges,
        remainingNodes: data.remaining,
        isLoading: false,
        expansionState: {},
        focalNodeId: null,
        selectedNode: null,
        overviewLimit: data.nodes.length || INITIAL_GRAPH_LIMIT,
      });
    } catch (e) {
      set({ error: String(e), isLoading: false });
    }
  },

  loadMoreOverview: async () => {
    const { focalNodeId, overviewLimit, isLoading } = get();
    if (focalNodeId || isLoading) return;

    set({ isLoading: true, error: null });
    try {
      const nextLimit = overviewLimit + INITIAL_GRAPH_LIMIT;
      const data = await fetchInitialGraph(nextLimit);
      const visibleIds = new Set(data.nodes.map((n) => n.id));

      set({
        nodes: data.nodes,
        edges: data.edges,
        visibleNodeIds: visibleIds,
        renderMode: data.render_mode,
        totalNodes: data.total_nodes,
        totalEdges: data.total_edges,
        remainingNodes: data.remaining,
        overviewLimit: data.nodes.length || nextLimit,
        isLoading: false,
      });
    } catch (e) {
      set({ error: String(e), isLoading: false });
    }
  },

  loadFocalSubgraph: async (nodeId: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await fetchFocalSubgraph(nodeId, NEIGHBOR_PAGE_SIZE);
      const visibleIds = new Set(data.nodes.map((n) => n.id));

      set({
        nodes: data.nodes,
        edges: data.edges,
        visibleNodeIds: visibleIds,
        focalNodeId: nodeId,
        selectedNode: data.nodes.find((n) => n.id === nodeId) || null,
        isLoading: false,
        expansionState: {
          [nodeId]: {
            totalNeighbors: data.total_neighbors,
            shownNeighbors: data.neighbors_shown,
            offset: data.neighbors_shown,
            hasMore: data.has_more,
          },
        },
      });
    } catch (e) {
      set({ error: String(e), isLoading: false });
    }
  },

  expandNodeNeighbors: async (nodeId: string) => {
    const { visibleNodeIds, nodes, edges, expansionState } = get();
    const current = expansionState[nodeId] || { totalNeighbors: 0, shownNeighbors: 0, offset: 0, hasMore: true };

    if (!current.hasMore && current.totalNeighbors > 0) return;

    try {
      const excludeArray = Array.from(visibleNodeIds);
      const data = await expandNode(nodeId, excludeArray, current.offset, NEIGHBOR_PAGE_SIZE);
      if (data.new_nodes.length === 0 && !data.has_more) return;

      const newVisibleIds = new Set(visibleNodeIds);
      for (const n of data.new_nodes) {
        newVisibleIds.add(n.id);
      }

      set({
        nodes: [...nodes, ...data.new_nodes],
        edges: [...edges, ...data.new_edges],
        visibleNodeIds: newVisibleIds,
        expansionState: {
          ...expansionState,
          [nodeId]: {
            totalNeighbors: data.total_neighbors,
            shownNeighbors: current.shownNeighbors + data.neighbors_returned,
            offset: data.next_offset,
            hasMore: data.has_more,
          },
        },
      });
    } catch (e) {
      console.error("Expand failed:", e);
    }
  },

  highlightNodes: (ids: string[]) => {
    set({ highlightedNodeIds: new Set(ids) });
    setTimeout(() => {
      set((state) => {
        const current = state.highlightedNodeIds;
        const newSet = new Set(current);
        for (const id of ids) newSet.delete(id);
        return { highlightedNodeIds: newSet };
      });
    }, 8000);
  },

  selectNode: (node: GraphNode | null) => {
    set({ selectedNode: node });
  },

  clearHighlights: () => {
    set({ highlightedNodeIds: new Set() });
  },

  resetGraph: () => {
    set({
      nodes: [],
      edges: [],
      visibleNodeIds: new Set(),
      highlightedNodeIds: new Set(),
      selectedNode: null,
      focalNodeId: null,
      expansionState: {},
      remainingNodes: 0,
      overviewLimit: INITIAL_GRAPH_LIMIT,
      error: null,
    });
  },
}));
