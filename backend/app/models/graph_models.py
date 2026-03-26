from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List


class NodeMetadata(BaseModel):
    type: str
    label: str
    properties: Dict[str, Any]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    metadata: NodeMetadata
    degree: int = 0
    is_anomaly: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    properties: Dict[str, Any] = {}


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int
    render_mode: str
    remaining: int = 0  # How many more nodes are available


class ExpandNodeResponse(BaseModel):
    new_nodes: List[GraphNode]
    new_edges: List[GraphEdge]
    node_id: str
    neighbors_returned: int
    total_neighbors: int
    has_more: bool
    next_offset: int


class SearchHit(BaseModel):
    id: str
    type: str
    label: str
    degree: int = 0
    total_neighbors: int = 0


class FocalSubgraph(BaseModel):
    focal_node: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    neighbors_shown: int
    total_neighbors: int
    has_more: bool


class SearchResponse(BaseModel):
    results: List[SearchHit]
    count: int
    focal_subgraph: Optional[FocalSubgraph] = None


class HighlightRequest(BaseModel):
    node_ids: List[str]


class AnomalyItem(BaseModel):
    type: str
    sales_order: Optional[str] = None
    delivery_document: Optional[str] = None
    billing_document: Optional[str] = None
    accounting_document: Optional[str] = None
    description: str = ""


class AnomalyResponse(BaseModel):
    incomplete_flows: List[AnomalyItem]
    total_count: int
    description: str


class StatsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    nodes_by_type: Dict[str, int]
    edges_by_type: Dict[str, int]
    anomaly_counts: Dict[str, int]
    date_range: Dict[str, str]
