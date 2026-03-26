import logging
from app.models.chat_models import DomainClassification

logger = logging.getLogger(__name__)


DOMAIN_ENTITIES = [
    "sales order",
    "delivery",
    "billing",
    "invoice",
    "payment",
    "journal entry",
    "customer",
    "business partner",
    "product",
    "material",
    "plant",
    "warehouse",
    "order-to-cash",
    "o2c",
    "accounts receivable",
    "shipment",
    "cancellation",
    "quantity",
    "amount",
    "net amount",
    "price",
    "currency",
    "INR",
]

OFF_TOPIC_SIGNALS = [
    "weather",
    "recipe",
    "cooking",
    "movie",
    "song",
    "joke",
    "story",
    "poem",
    "history",
    "geography",
    "sports",
    "football",
    "cricket",
    "politics",
    "election",
    "president",
    "prime minister",
    "celebrity",
    "movie star",
    "game",
    "play",
    "music",
    "dance",
    "sing",
    "write a poem",
    "tell me a story",
    "what is the",
    "who is",
    "where is",
    "when was",
    "how to",
    "explain",
    "define",
    "meaning of",
    "capital of",
    "population",
    "translate",
    "convert",
    "calculate",
    "solve",
    "python",
    "javascript",
    "code",
    "program",
    "algorithm",
    "today",
    "tomorrow",
    "yesterday",
    "temperature",
    "rain",
    "sunny",
]


def classify_query_offline(message: str) -> DomainClassification:
    """Fast offline domain classification without LLM."""
    msg_lower = message.lower()

    # Check for off-topic signals first
    off_topic_score = 0
    for signal in OFF_TOPIC_SIGNALS:
        if signal in msg_lower:
            off_topic_score += 1

    # Check for domain-relevant signals
    domain_score = 0
    matched_entities = []
    for entity in DOMAIN_ENTITIES:
        if entity in msg_lower:
            domain_score += 1
            matched_entities.append(entity)

    # Check for ID patterns (SO numbers, billing docs, etc.)
    import re

    id_patterns = [
        (r"\b7\d{5}\b", "SalesOrder"),
        (r"\b8\d{7}\b", "DeliveryDoc"),
        (r"\b9\d{7}\b", "BillingDoc"),
        (r"\b94\d{8}\b", "JournalEntry"),
        (r"\b3\d{8}\b", "Customer"),
    ]
    extracted_ids = []
    for pattern, id_type in id_patterns:
        matches = re.findall(pattern, message)
        for m in matches:
            extracted_ids.append(f"{id_type}_{m}")
            domain_score += 2  # IDs are strong signals

    # Domain keywords that indicate business queries
    business_keywords = [
        "which",
        "what",
        "how many",
        "count",
        "total",
        "list",
        "show",
        "find",
        "trace",
        "track",
        "follow",
        "complete",
        "incomplete",
        "missing",
        "broken",
        "anomal",
        "highest",
        "lowest",
        "most",
        "least",
        "top",
        "all",
        "associated",
        "connected",
        "flow",
        "chain",
        "status",
    ]
    for kw in business_keywords:
        if kw in msg_lower:
            domain_score += 1

    # Decision logic
    if domain_score == 0 and off_topic_score > 0:
        return DomainClassification(
            is_relevant=False,
            query_type="off_topic",
            extracted_entities=[],
            extracted_ids=[],
            confidence=0.95,
            reason="Query contains no domain-relevant terms and matches off-topic patterns",
        )

    if off_topic_score > domain_score and domain_score <= 1:
        return DomainClassification(
            is_relevant=False,
            query_type="off_topic",
            extracted_entities=[],
            extracted_ids=[],
            confidence=0.85,
            reason="Query has more off-topic signals than domain signals",
        )

    if domain_score == 0 and off_topic_score == 0:
        # Ambiguous - default to off-topic for safety
        return DomainClassification(
            is_relevant=False,
            query_type="off_topic",
            extracted_entities=[],
            extracted_ids=[],
            confidence=0.7,
            reason="Query could not be classified as domain-relevant",
        )

    # Determine query type
    query_type = "lookup"
    # Check anomaly BEFORE trace (more specific)
    if any(w in msg_lower for w in ["anomal", "incomplete", "broken", "missing", "gap", "delivered but not billed", "not billed", "billed but not"]):
        query_type = "anomaly"
    elif any(w in msg_lower for w in ["trace", "track", "follow", "chain", "flow"]):
        query_type = "trace"
    elif any(w in msg_lower for w in ["most", "highest", "top", "count", "total", "how many", "aggregate", "number of"]):
        query_type = "aggregate"
    elif any(w in msg_lower for w in ["compare", "versus", "vs", "difference", "between"]):
        query_type = "comparison"

    confidence = min(0.95, 0.5 + (domain_score * 0.1) - (off_topic_score * 0.15))

    return DomainClassification(
        is_relevant=True,
        query_type=query_type,
        extracted_entities=matched_entities,
        extracted_ids=extracted_ids,
        confidence=max(0.5, confidence),
        reason=f"Domain-relevant query with {domain_score} matching signals",
    )
