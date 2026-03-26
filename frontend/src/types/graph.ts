export interface NodeMetadata {
  type: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  metadata: NodeMetadata;
  degree: number;
  is_anomaly: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  properties: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  render_mode: "push" | "pull";
  remaining: number;
}

export interface ExpandNodeResponse {
  new_nodes: GraphNode[];
  new_edges: GraphEdge[];
  node_id: string;
  neighbors_returned: number;
  total_neighbors: number;
  has_more: boolean;
  next_offset: number;
}

export interface SearchHit {
  id: string;
  type: string;
  label: string;
  degree: number;
  total_neighbors: number;
}

export interface FocalSubgraph {
  focal_node: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  neighbors_shown: number;
  total_neighbors: number;
  has_more: boolean;
}

export interface SearchResponse {
  results: SearchHit[];
  count: number;
  focal_subgraph: FocalSubgraph | null;
}

export interface StatsResponse {
  total_nodes: number;
  total_edges: number;
  nodes_by_type: Record<string, number>;
  edges_by_type: Record<string, number>;
  anomaly_counts: Record<string, number>;
  date_range: Record<string, string>;
}

// Chat types
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  thought?: string;
  sql?: string;
  sources?: string[];
  highlighted_ids?: string[];
  focal_node_id?: string;
  query_type?: string;
  confidence?: number;
  is_guardrailed?: boolean;
}

export interface SSEThought {
  thought: string;
}

export interface SSESQl {
  sql: string;
  explanation: string;
}

export interface SSEResult {
  rows: Record<string, unknown>[];
  row_count: number;
  columns: string[];
}

export interface SSEAnswer {
  answer: string;
  sql_used?: string;
  sources?: string[];
  highlighted_node_ids?: string[];
  focal_node_id?: string;
  query_type?: string;
  confidence?: number;
}
