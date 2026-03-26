import type {
  GraphResponse,
  ExpandNodeResponse,
  SearchResponse,
  FocalSubgraph,
  StatsResponse,
} from "../types/graph";

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL?.trim() || "/api";
const API_BASE = RAW_API_BASE.endsWith("/")
  ? RAW_API_BASE.slice(0, -1)
  : RAW_API_BASE;
const PAGE_SIZE = 10;

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function fetchInitialGraph(limit: number = PAGE_SIZE): Promise<GraphResponse> {
  const res = await fetch(apiUrl(`/graph/initial?limit=${limit}`));
  if (!res.ok) throw new Error(`Failed to fetch graph: ${res.statusText}`);
  return res.json();
}

export async function expandNode(
  nodeId: string,
  excludeIds: string[],
  offset: number = 0,
  limit: number = PAGE_SIZE
): Promise<ExpandNodeResponse> {
  const exclude = excludeIds.join(",");
  const res = await fetch(
    apiUrl(`/graph/expand/${encodeURIComponent(nodeId)}?exclude=${encodeURIComponent(exclude)}&offset=${offset}&limit=${limit}`)
  );
  if (!res.ok) throw new Error(`Failed to expand node: ${res.statusText}`);
  return res.json();
}

export async function fetchFocalSubgraph(nodeId: string, limit: number = PAGE_SIZE): Promise<FocalSubgraph> {
  const res = await fetch(
    apiUrl(`/graph/focal/${encodeURIComponent(nodeId)}?limit=${limit}`)
  );
  if (!res.ok) throw new Error(`Failed to fetch focal subgraph: ${res.statusText}`);
  return res.json();
}

export async function searchNodes(q: string): Promise<SearchResponse> {
  const res = await fetch(apiUrl(`/graph/search?q=${encodeURIComponent(q)}`));
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
  return res.json();
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(apiUrl("/graph/stats"));
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
  return res.json();
}

export async function sendChatMessage(
  message: string,
  sessionId: string,
  onThought: (thought: string) => void,
  onSql: (sql: string, explanation: string) => void,
  onResult: (rows: Record<string, unknown>[], count: number, columns: string[]) => void,
  onAnswer: (
    answer: string,
    sources: string[],
    highlightedIds: string[],
    queryType: string,
    focalNodeId?: string
  ) => void,
  onError: (error: string) => void
): Promise<void> {
  const response = await fetch(apiUrl("/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6).trim();
        if (!data) continue;

        try {
          const parsed = JSON.parse(data);
          switch (currentEvent) {
            case "thought":
              onThought(parsed.thought);
              break;
            case "sql":
              onSql(parsed.sql, parsed.explanation);
              break;
            case "result":
              onResult(parsed.rows, parsed.row_count, parsed.columns);
              break;
            case "answer":
              onAnswer(
                parsed.answer,
                parsed.sources || [],
                parsed.highlighted_node_ids || [],
                parsed.query_type || "",
                parsed.focal_node_id
              );
              break;
            case "error":
              onError(parsed.error);
              break;
          }
        } catch {
          // Skip unparseable lines
        }
      }
    }
  }
}
