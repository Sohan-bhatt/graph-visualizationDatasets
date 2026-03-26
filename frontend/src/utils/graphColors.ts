export const NODE_COLORS: Record<string, string> = {
  SalesOrder: "#3B82F6",
  DeliveryDoc: "#10B981",
  BillingDoc: "#F59E0B",
  JournalEntry: "#8B5CF6",
  Payment: "#22D3EE",
  Customer: "#EF4444",
  Product: "#6B7280",
  Plant: "#84CC16",
};

export const ANOMALY_COLOR = "#FF0000";
export const HIGHLIGHT_COLOR = "#FBBF24";
export const DEFAULT_NODE_COLOR = "#9CA3AF";

export function getNodeColor(type: string, isAnomaly: boolean, isHighlighted: boolean): string {
  if (isAnomaly) return ANOMALY_COLOR;
  if (isHighlighted) return HIGHLIGHT_COLOR;
  return NODE_COLORS[type] || DEFAULT_NODE_COLOR;
}

export function getNodeSize(degree: number): number {
  return Math.max(4, Math.min(12, 3 + degree * 0.5));
}
