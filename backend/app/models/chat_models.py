from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Union
import re


class UserQuery(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="default")

    @field_validator("message")
    @classmethod
    def no_prompt_injection(cls, v: str) -> str:
        injection_patterns = [
            r"ignore (previous|all|above) instructions",
            r"you are now",
            r"act as",
            r"jailbreak",
            r"</?(system|human|assistant)>",
            r"SYSTEM PROMPT",
        ]
        for pattern in injection_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Invalid query format")
        return v.strip()


class DomainClassification(BaseModel):
    is_relevant: bool
    query_type: Literal[
        "lookup", "trace", "anomaly", "aggregate", "comparison", "off_topic"
    ]
    extracted_entities: List[str] = Field(default_factory=list)
    extracted_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class GeneratedSQL(BaseModel):
    sql: str
    explanation: str
    tables_used: List[str]
    estimated_result_type: Literal["table", "single_value", "trace_chain", "empty"]

    @field_validator("sql")
    @classmethod
    def validate_sql_safety(cls, v: str) -> str:
        sql_upper = v.upper()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "EXEC",
            "EXECUTE",
            "--",
            ";--",
        ]
        for keyword in forbidden:
            if keyword in sql_upper:
                raise ValueError(f"Unsafe SQL keyword detected: {keyword}")
        if not sql_upper.strip().startswith("SELECT"):
            raise ValueError("Only SELECT queries are permitted")
        return v


class QueryResult(BaseModel):
    rows: List[Dict]
    row_count: int
    columns: List[str]
    truncated: bool = False


class AgentResponse(BaseModel):
    answer: str
    thought_process: str = ""
    sql_used: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    highlighted_node_ids: List[str] = Field(default_factory=list)
    focal_node_id: Optional[str] = None
    query_type: str = ""
    confidence: float = 0.0
    is_guardrailed: bool = False


GUARDRAIL_RESPONSE = AgentResponse(
    answer="This system is designed to answer questions related to the provided SAP Order-to-Cash dataset only. You can ask about Sales Orders, Deliveries, Billing Documents, Payments, Customers, or Products.",
    thought_process="Query classified as off-topic. Domain guardrail activated.",
    query_type="off_topic",
    confidence=1.0,
    is_guardrailed=True,
)
