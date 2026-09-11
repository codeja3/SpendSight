import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Literal

# Our strict LLM extraction schema (from SPEC.md)
class TransactionEntity(BaseModel):
    vendor: str = Field(
        description="The clean, normalized name of the business. Strip out store numbers, cities, or payment processor prefixes like 'SQ *' or 'TST*'."
    )
    category: Literal[
        "Groceries", "Dining", "Transportation", "Housing", 
        "Utilities", "Entertainment", "Shopping", "Income", "Transfer", "Other"
    ] = Field(
        description="The budget category that best fits the vendor."
    )

class BatchTransactionEntities(BaseModel):
    items: list[TransactionEntity]

# Initialize the local Ollama client wrapped with Instructor
# We point the base_url to Ollama's default local OpenAI-compatible API endpoint
client = instructor.from_openai(
    OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # required by the OpenAI SDK, but ignored by Ollama
    ),
    mode=instructor.Mode.JSON,
)

def _get_cached_vendors(raw_descriptions: list[str], db_path: str) -> dict[str, TransactionEntity]:
    """Look up raw descriptions in the vendor_cache table."""
    import sqlite3
    cached = {}
    try:
        with sqlite3.connect(db_path) as conn:
            # Ensure vendor_cache table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vendor_cache (
                    raw_description TEXT PRIMARY KEY,
                    vendor TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in raw_descriptions)
            if placeholders:
                cursor.execute(
                    f"SELECT raw_description, vendor, category FROM vendor_cache WHERE raw_description IN ({placeholders})",
                    raw_descriptions
                )
                for row in cursor.fetchall():
                    cached[row[0]] = TransactionEntity(vendor=row[1], category=row[2])
    except Exception:
        pass
    return cached

def _save_cached_vendors(entities: dict[str, TransactionEntity], db_path: str) -> None:
    """Persist newly normalized vendors to the vendor_cache table."""
    import sqlite3
    if not entities:
        return
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            records = [
                (raw, entity.vendor, entity.category)
                for raw, entity in entities.items()
            ]
            cursor.executemany(
                "INSERT OR REPLACE INTO vendor_cache (raw_description, vendor, category) VALUES (?, ?, ?)",
                records
            )
            conn.commit()
    except Exception:
        pass

def normalize_vendor(raw_description: str, model: str = "gemma4:e2b") -> TransactionEntity:
    """Sends the raw description to the local LLM and returns a structured entity."""
    entity = client.chat.completions.create(
        model=model,
        response_model=TransactionEntity,
        messages=[
            {
                "role": "system",
                "content": "You are a precise financial categorization API. Normalize the vendor name and map it to the correct category. Do not hallucinate."
            },
            {
                "role": "user",
                "content": f"Raw Bank Transaction: {raw_description}"
            }
        ],
        max_retries=2
    )
    return entity

def normalize_batch(raw_descriptions: list[str], model: str = "gemma4:e2b") -> list[TransactionEntity]:
    """Normalizes a micro-batch of raw descriptions in a single LLM call."""
    if not raw_descriptions:
        return []

    prompt_lines = [f"{i+1}. {desc}" for i, desc in enumerate(raw_descriptions)]
    content_str = "\n".join(prompt_lines)

    batch_result = client.chat.completions.create(
        model=model,
        response_model=BatchTransactionEntities,
        messages=[
            {
                "role": "system",
                "content": "You are a precise financial categorization API. Normalize each raw vendor string into a clean vendor and budget category. Return items in the exact same order."
            },
            {
                "role": "user",
                "content": f"Raw Bank Transactions:\n{content_str}"
            }
        ],
        max_retries=2
    )
    if hasattr(batch_result, "items"):
        return batch_result.items
    elif isinstance(batch_result, list):
        return batch_result
    elif isinstance(batch_result, TransactionEntity):
        return [batch_result]
    return []

def normalize_transactions(
    raw_descriptions: list[str],
    db_path: str = "spendsight.db",
    batch_size: int = 15,
    model: str = "gemma4:e2b"
) -> list[TransactionEntity]:
    """
    Normalizes raw descriptions with SQLite vendor cache lookups and micro-batched LLM calls.
    Maintains exact 1-to-1 input order.
    """
    if not raw_descriptions:
        return []

    # 1. Lookup cached vendors
    cache = _get_cached_vendors(raw_descriptions, db_path)

    # 2. Identify unique cache misses while keeping track of indices
    misses: list[str] = []
    seen_misses = set()
    for desc in raw_descriptions:
        if desc not in cache and desc not in seen_misses:
            misses.append(desc)
            seen_misses.add(desc)

    # 3. Process misses in micro-batches
    newly_resolved: dict[str, TransactionEntity] = {}
    for i in range(0, len(misses), batch_size):
        batch = misses[i : i + batch_size]
        resolved = normalize_batch(batch, model=model)
        for desc, ent in zip(batch, resolved):
            newly_resolved[desc] = ent

    # 4. Save newly resolved entities to cache
    if newly_resolved:
        _save_cached_vendors(newly_resolved, db_path)
        cache.update(newly_resolved)

    # 5. Assemble final list matching original order
    results = []
    for desc in raw_descriptions:
        if desc in cache:
            results.append(cache[desc])
        else:
            # Fallback if batch count mismatch
            results.append(TransactionEntity(vendor=desc, category="Other"))

    return results