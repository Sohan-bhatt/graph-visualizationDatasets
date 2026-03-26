import os
import json
import logging
<<<<<<< HEAD
import google.generativeai as genai
=======
>>>>>>> 2c6ca51 (inital commit)
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from app.models.chat_models import (
    UserQuery,
    DomainClassification,
    GeneratedSQL,
    QueryResult,
    AgentResponse,
    GUARDRAIL_RESPONSE,
)
from app.services.guardrails import classify_query_offline
from app.services.sql_executor import execute_sql, extract_entity_ids, extract_entity_ids_from_text, normalize_entity_id

logger = logging.getLogger(__name__)

SCHEMA_CONTEXT: dict = {}
MODEL: Optional[object] = None
LLM_PROVIDER: str = "none"


# ═══════════════════════════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════════════════════════

def load_schema_context():
    global SCHEMA_CONTEXT
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema_context.json")
    try:
        with open(schema_path, "r") as f:
            SCHEMA_CONTEXT = json.load(f)
        logger.info("Schema context loaded")
    except FileNotFoundError:
        logger.warning("Schema context file not found")
        SCHEMA_CONTEXT = {}


def init_llm():
    """Initialize LLM (OpenAI preferred, fallback to Gemini)."""
    global MODEL, LLM_PROVIDER
    
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and not openai_key.startswith("AIza"):
        MODEL = AsyncOpenAI(api_key=openai_key)
        LLM_PROVIDER = "openai"
        logger.info("OpenAI client initialized (gpt-4o-mini)")
        return MODEL
    
<<<<<<< HEAD
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        genai.configure(api_key=gemini_key)
        MODEL = genai.GenerativeModel("gemini-2.0-flash")
        LLM_PROVIDER = "gemini"
        logger.info("Gemini 2.0 Flash initialized")
        return MODEL
=======
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            MODEL = genai.GenerativeModel("gemini-2.0-flash")
            LLM_PROVIDER = "gemini"
            logger.info("Gemini 2.0 Flash initialized")
            return MODEL
>>>>>>> 2c6ca51 (inital commit)
    
    logger.warning("No LLM API key set — LLM features disabled")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

CLASSIFY_PROMPT = """You are a domain classifier for a SAP Order-to-Cash (O2C) data system.

The system contains ONLY these entity types:
- Sales Orders (IDs: 6 digits starting with 7, e.g. 740506)
- Outbound Deliveries (IDs: 8 digits starting with 8, e.g. 80737721)
- Billing Documents (IDs: 8 digits starting with 9, e.g. 90504248) — types: F2=invoice, S1=cancellation
- Journal Entries (IDs: 10 digits starting with 94, e.g. 9400000220)
- Payments (clearing documents)
- Customers (IDs: 9 digits starting with 3, e.g. 320000083)
- Products/Materials (IDs like S8907367001003 or 7-digit numbers)
- Plants (IDs like 1920, WB05)

CLASSIFY as is_relevant=false ONLY for clearly off-topic queries:
- General knowledge (history, science, geography, math)
- Creative writing, jokes, stories
- Questions about people, politics, sports, weather, cooking
- Programming help unrelated to this data
- Any topic not about the entities listed above

CLASSIFY as is_relevant=true for ANY query that could reasonably be answered from this dataset,
even if phrased informally or ambiguously.

Respond with ONLY this JSON (no markdown, no explanation):
{"is_relevant":bool,"query_type":"lookup|trace|anomaly|aggregate|comparison|off_topic","extracted_entities":string[],"extracted_ids":string[],"confidence":0.0-1.0,"reason":string}"""


def build_sql_prompt(schema_str: str) -> str:
    return f"""You are an expert SQLite query generator for a SAP Order-to-Cash database.

DATABASE SCHEMA:
{schema_str}

CRITICAL DATA RELATIONSHIPS:
1. SalesOrder → Delivery: outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder
2. Delivery → Billing: billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument
3. Billing → Journal: journal_entry_items.referenceDocument = billing_document_headers.billingDocument
4. Billing accounting link: billing_document_headers.accountingDocument = journal_entry_items.accountingDocument
5. Journal → Payment: journal_entry_items.clearingAccountingDocument = payments.clearingAccountingDocument
6. Customer link: sales_order_headers.soldToParty = business_partners.businessPartner
7. Product link: sales_order_items.material = products.product

CRITICAL NOTES:
- billing_document_items.referenceSdDocument → points to DELIVERY doc (NOT sales order!)
- outbound_delivery_items.referenceSdDocument → points to SALES ORDER
- journal_entry_items.referenceDocument → points to BILLING doc
- billingDocumentIsCancelled: 1=cancelled, 0=active
- billingDocumentType: F2=invoice, S1=cancellation reversal

RULES:
1. ONLY use tables/columns from the schema above
2. Always add LIMIT 100
3. For trace queries: use LEFT JOINs to show full chain, NULLs show gaps
4. For anomaly/incomplete queries: LEFT JOIN + WHERE ... IS NULL
5. JOIN product_descriptions WHERE language='EN' for readable names
6. Use table aliases for readability (soh, odi, odh, bdi, bdh, je, pay)
7. Column aliases: use AS for computed columns (e.g. COUNT(...) as count)

Respond with ONLY this JSON (no markdown, no explanation):
{{"sql":"SELECT ...","explanation":"This query...","tables_used":["t1","t2"]}}"""


VERIFY_PROMPT = """You are a SAP business analyst. Summarize the SQL query results for the user.

RULES:
- Use clear, professional English
- Cite specific IDs, amounts (INR), dates from the data
- For trace queries: describe the flow step by step (Order → Delivery → Billing → Payment)
- For aggregate queries: highlight the top results with counts/amounts
- For anomaly queries: explain what is broken/incomplete
- NEVER invent data not in the results
- If results are empty: say "No matching records found in the dataset"
- Keep it concise but informative (3-8 sentences)
- Format: use bullet points for lists of items"""


RETRY_PROMPT_TEMPLATE = """The previous SQL query failed or returned no results.

Original question: {question}
Previous SQL: {sql}
Error: {error}

Please generate a CORRECTED SQL query that fixes the issue. Common fixes:
- Check table names and column names match the schema exactly
- Verify JOIN conditions use the correct foreign keys
- Check for typos in column names
- Use LEFT JOIN instead of INNER JOIN if rows are being excluded
- Verify the WHERE clause matches actual data values (e.g. dates, IDs)

Respond with ONLY this JSON:
{{"sql":"SELECT ...","explanation":"Corrected query that...","tables_used":["t1","t2"]}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CALLS
# ═══════════════════════════════════════════════════════════════════════════════

async def call_llm_json(system_prompt: str, user_msg: str, temperature: float = 0.2, max_tokens: int = 1500) -> Optional[dict]:
    """Call LLM (OpenAI or Gemini) and parse JSON response."""
    global MODEL, LLM_PROVIDER
    
    try:
        if LLM_PROVIDER == "openai":
            response = await MODEL.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
        else:
            response = MODEL.generate_content(
                [system_prompt, user_msg],
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = response.text.strip()
        
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        # Extract JSON from response (may have surrounding text)
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)
        return json.loads(text)
    except Exception as e:
        logger.error(f"LLM JSON call failed: {e}")
        return None


async def call_llm_text(system_prompt: str, user_msg: str, temperature: float = 0.3, max_tokens: int = 1200) -> Optional[str]:
    """Call LLM (OpenAI or Gemini) and return plain text."""
    global MODEL, LLM_PROVIDER
    
    try:
        if LLM_PROVIDER == "openai":
            response = await MODEL.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        else:
            response = MODEL.generate_content(
                [system_prompt, user_msg],
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text.strip()
    except Exception as e:
        logger.error(f"LLM text call failed: {e}")
        return None


# Legacy aliases
async def call_gemini_json(model, system_prompt: str, user_msg: str, temperature: float = 0.2, max_tokens: int = 1500) -> Optional[dict]:
    return await call_llm_json(system_prompt, user_msg, temperature, max_tokens)

async def call_gemini_text(model, system_prompt: str, user_msg: str, temperature: float = 0.3, max_tokens: int = 1200) -> Optional[str]:
    return await call_llm_text(system_prompt, user_msg, temperature, max_tokens)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1: CLASSIFY
# ═══════════════════════════════════════════════════════════════════════════════

async def classify_query(query: str) -> DomainClassification:
    """Classify user query using LLM."""
    data = await call_llm_json(
        CLASSIFY_PROMPT,
        f"Classify this user query: {query}",
        temperature=0.1,
        max_tokens=300,
    )

    if data and "is_relevant" in data:
        try:
            return DomainClassification(**data)
        except Exception as e:
            logger.warning(f"Classification validation failed: {e}")

    # Fallback to offline classifier
    logger.info("Falling back to offline classifier")
    return classify_query_offline(query)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2: GENERATE SQL
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_sql(
    query: str,
    classification: DomainClassification,
    previous_error: Optional[str] = None,
    previous_sql: Optional[str] = None,
) -> Optional[GeneratedSQL]:
    """Generate SQL using LLM. Can self-correct if previous_error is provided."""
    schema_str = json.dumps(SCHEMA_CONTEXT, indent=2)[:10000]

    if previous_error and previous_sql:
        # Self-correction mode
        prompt = RETRY_PROMPT_TEMPLATE.format(
            question=query,
            sql=previous_sql,
            error=previous_error,
        )
        logger.info(f"Self-correcting SQL. Previous error: {previous_error[:200]}")
    else:
        # Normal generation
        prompt = build_sql_prompt(schema_str)

    user_msg = (
        f"Query type: {classification.query_type}\n"
        f"Extracted IDs: {classification.extracted_ids}\n"
        f"User question: {query}"
    )

    data = await call_llm_json(prompt, user_msg, temperature=0.15, max_tokens=1500)

    if data and "sql" in data:
        try:
            return GeneratedSQL(
                sql=data["sql"],
                explanation=data.get("explanation", ""),
                tables_used=data.get("tables_used", []),
                estimated_result_type=data.get("estimated_result_type", "table"),
            )
        except Exception as e:
            logger.warning(f"SQL validation failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3: VERIFY & FORMAT ANSWER
# ═══════════════════════════════════════════════════════════════════════════════

async def format_answer(query: str, sql: str, result: QueryResult) -> str:
    """Format SQL results into natural language using LLM."""
    results_str = json.dumps(result.rows[:30], indent=2, default=str)[:6000]
    user_msg = (
        f"User question: {query}\n\n"
        f"SQL executed: {sql}\n\n"
        f"Results ({result.row_count} rows returned, showing up to 30):\n{results_str}"
    )

    answer = await call_llm_text(VERIFY_PROMPT, user_msg, temperature=0.3, max_tokens=1200)

    if answer:
        return answer

    # Fallback formatting
    return format_results_offline(result)


def format_results_offline(result: QueryResult) -> str:
    """Format results without LLM."""
    if result.row_count == 0:
        return "No matching records found in the dataset."

    lines = [f"Found {result.row_count} result(s):\n"]
    for i, row in enumerate(result.rows[:15], 1):
        parts = []
        for k, v in row.items():
            if v is not None:
                parts.append(f"{k}: {v}")
        lines.append(f"{i}. {', '.join(parts)}")

    if result.truncated:
        lines.append(f"\n... (showing first {len(result.rows)} rows)")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE — with self-correction
# ═══════════════════════════════════════════════════════════════════════════════

MAX_RETRIES = 2


def merge_highlight_ids(query_message: str, extracted_ids: list[str], result_rows: list[dict]) -> list[str]:
    """Put explicitly queried entities first, then append result-derived entities."""
    ordered: list[str] = []

    for raw_id in extracted_ids:
        node_id = normalize_entity_id(raw_id)
        if node_id and node_id not in ordered:
            ordered.append(node_id)

    for node_id in extract_entity_ids_from_text(query_message):
        if node_id not in ordered:
            ordered.append(node_id)

    for node_id in extract_entity_ids(result_rows):
        if node_id not in ordered:
            ordered.append(node_id)

    return ordered


async def run_agent(db_path: str, query: UserQuery) -> AgentResponse:
    """Run the full pipeline: classify → SQL → execute → verify. Self-corrects on failure."""
    model = init_llm()

    # ── Guardrail: no API key ──
    if not model:
        return AgentResponse(
            answer="GEMINI_API_KEY is not configured. Please add your API key to backend/.env to enable the LLM query system.",
            thought_process="No Gemini API key found",
            query_type="error",
            confidence=0.0,
        )

    # ── Stage 1: Classify ──
    classification = await classify_query(query.message)
    logger.info(f"Classification: {classification}")

    if not classification.is_relevant or classification.confidence < 0.5:
        return GUARDRAIL_RESPONSE

    # ── Stage 2: Generate SQL (with self-correction loop) ──
    generated_sql = None
    last_error = None
    last_sql = None

    for attempt in range(MAX_RETRIES + 1):
        generated_sql = await generate_sql(
            query.message, classification,
            previous_error=last_error,
            previous_sql=last_sql,
        )

        if not generated_sql:
            if attempt < MAX_RETRIES:
                last_error = "LLM returned invalid or unparseable JSON"
                last_sql = "N/A"
                logger.warning(f"SQL generation attempt {attempt + 1} failed, retrying...")
                continue
            else:
                return AgentResponse(
                    answer="I was unable to generate a valid SQL query for your question after multiple attempts. Please try rephrasing your question.",
                    thought_process="SQL generation failed after all retries",
                    query_type=classification.query_type,
                    confidence=0.2,
                )

        # ── Stage 3: Execute SQL ──
        exec_result = await execute_sql(db_path, generated_sql.sql)

        if "error" in exec_result:
            last_error = exec_result["error"]
            last_sql = generated_sql.sql
            logger.warning(f"SQL execution attempt {attempt + 1} failed: {last_error[:200]}")
            if attempt < MAX_RETRIES:
                continue
            else:
                return AgentResponse(
                    answer=f"I generated a query but it failed to execute. Error: {exec_result['error']}",
                    thought_process=f"SQL execution failed after {MAX_RETRIES + 1} attempts",
                    sql_used=generated_sql.sql,
                    sources=generated_sql.tables_used,
                    query_type=classification.query_type,
                    confidence=0.2,
                )

        query_result = QueryResult(
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
            columns=exec_result["columns"],
            truncated=exec_result.get("truncated", False),
        )

        # If empty results, try self-correcting (maybe wrong JOIN or WHERE)
        if query_result.row_count == 0 and attempt < MAX_RETRIES:
            last_error = "Query returned 0 results. The JOIN conditions or WHERE clause may be incorrect, or the entity/ID doesn't exist in the data."
            last_sql = generated_sql.sql
            logger.info(f"SQL returned 0 rows on attempt {attempt + 1}, retrying with self-correction...")
            continue

        # Success — got results (or confirmed empty after retries)
        break

    # ── Stage 4: Format answer ──
    highlighted_ids = merge_highlight_ids(
        query.message,
        classification.extracted_ids,
        query_result.rows,
    )

    if query_result.row_count > 0:
        answer = await format_answer(query.message, generated_sql.sql, query_result)
    else:
        answer = (
            "I searched the dataset but found no matching records. "
            "This could mean:\n"
            "- The specific ID or entity doesn't exist in the data\n"
            "- The combination of criteria is too specific\n"
            "- The data covers a limited time range (March–July 2025)"
        )

    return AgentResponse(
        answer=answer,
        thought_process=f"Classified as '{classification.query_type}' ({classification.confidence:.0%}). Generated SQL using: {', '.join(generated_sql.tables_used)}. Found {query_result.row_count} results.",
        sql_used=generated_sql.sql,
        sources=generated_sql.tables_used,
        highlighted_node_ids=highlighted_ids,
        focal_node_id=highlighted_ids[0] if highlighted_ids else None,
        query_type=classification.query_type,
        confidence=classification.confidence,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SSE STREAMING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

async def run_agent_stream(db_path: str, query: UserQuery) -> AsyncGenerator[dict, None]:
    """Run agent pipeline with SSE streaming events."""
    model = init_llm()

    if not model:
        yield {"event": "answer", "data": {
            "answer": "GEMINI_API_KEY is not configured. Please add your API key to backend/.env.",
            "is_guardrailed": True,
            "query_type": "error",
            "confidence": 0.0,
        }}
        yield {"event": "done", "data": {}}
        return

    yield {"event": "thought", "data": {"thought": "Analyzing your question..."}}

    # ── Stage 1: Classify ──
    classification = await classify_query(query.message)
    logger.info(f"Classification: {classification}")

    if not classification.is_relevant or classification.confidence < 0.5:
        yield {"event": "thought", "data": {"thought": "Query is outside the dataset domain. This system only answers questions about SAP Order-to-Cash data."}}
        yield {"event": "answer", "data": GUARDRAIL_RESPONSE.model_dump()}
        yield {"event": "done", "data": {}}
        return

    yield {"event": "thought", "data": {"thought": f"Classified as '{classification.query_type}' ({classification.confidence:.0%}). Generating SQL query..."}}

    # ── Stage 2 & 3: Generate SQL + Execute with self-correction ──
    generated_sql = None
    query_result = None
    last_error = None
    last_sql = None

    for attempt in range(MAX_RETRIES + 1):
        generated_sql = await generate_sql(
            query.message, classification,
            previous_error=last_error,
            previous_sql=last_sql,
        )

        if not generated_sql:
            if attempt < MAX_RETRIES:
                last_error = "LLM returned invalid JSON"
                last_sql = "N/A"
                yield {"event": "thought", "data": {"thought": f"Retrying SQL generation (attempt {attempt + 2})..."}}
                continue
            else:
                yield {"event": "error", "data": {"error": "Failed to generate valid SQL after multiple attempts"}}
                yield {"event": "done", "data": {}}
                return

        yield {"event": "sql", "data": {"sql": generated_sql.sql, "explanation": generated_sql.explanation}}
        yield {"event": "thought", "data": {"thought": f"Executing query (attempt {attempt + 1})..."}}

        exec_result = await execute_sql(db_path, generated_sql.sql)

        if "error" in exec_result:
            last_error = exec_result["error"]
            last_sql = generated_sql.sql
            if attempt < MAX_RETRIES:
                yield {"event": "thought", "data": {"thought": f"Query had an error. Self-correcting... ({exec_result['error'][:80]})"}}
                continue
            else:
                yield {"event": "error", "data": {"error": exec_result["error"]}}
                yield {"event": "done", "data": {}}
                return

        query_result = QueryResult(
            rows=exec_result["rows"],
            row_count=exec_result["row_count"],
            columns=exec_result["columns"],
            truncated=exec_result.get("truncated", False),
        )

        if query_result.row_count == 0 and attempt < MAX_RETRIES:
            last_error = "Query returned 0 results. The JOINs or WHERE conditions may be filtering out all rows."
            last_sql = generated_sql.sql
            yield {"event": "thought", "data": {"thought": "Query returned no results. Adjusting query..."}}
            continue

        break

    # ── Emit intermediate results ──
    highlighted_ids = merge_highlight_ids(
        query.message,
        classification.extracted_ids,
        query_result.rows,
    )

    yield {
        "event": "result",
        "data": {
            "rows": query_result.rows[:10],
            "row_count": query_result.row_count,
            "columns": query_result.columns,
        },
    }

    # ── Stage 4: Format answer ──
    yield {"event": "thought", "data": {"thought": "Formatting answer from results..."}}

    if query_result.row_count > 0:
        answer = await format_answer(query.message, generated_sql.sql, query_result)
    else:
        answer = (
            "No matching records found in the dataset after multiple query attempts. "
            "The requested data may not exist in the available SAP O2C records (March–July 2025)."
        )

    yield {
        "event": "answer",
        "data": {
            "answer": answer,
            "sql_used": generated_sql.sql,
            "sources": generated_sql.tables_used,
            "highlighted_node_ids": highlighted_ids,
            "focal_node_id": highlighted_ids[0] if highlighted_ids else None,
            "query_type": classification.query_type,
            "confidence": classification.confidence,
        },
    }

    yield {"event": "done", "data": {}}
