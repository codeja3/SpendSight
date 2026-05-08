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

# Initialize the local Ollama client wrapped with Instructor
# We point the base_url to Ollama's default local OpenAI-compatible API endpoint
client = instructor.from_openai(
    OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # required by the OpenAI SDK, but ignored by Ollama
    ),
    mode=instructor.Mode.JSON,
)

def normalize_vendor(raw_description: str) -> TransactionEntity:
    """Sends the raw description to the local LLM and returns a structured entity."""
    
    # We query the local gemma4:e2b model and enforce the Pydantic schema
    entity = client.chat.completions.create(
        model="gemma4:e2b",
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
        max_retries=2 # Instructor will automatically retry and correct the LLM if it violates the Pydantic schema
    )
    
    return entity

def normalize_transactions(raw_descriptions: list[str]) -> list[TransactionEntity]:
    """
    Takes a list of raw vendor descriptions and processes them sequentially through the LLM.
    Returns a list of structured TransactionEntity objects in the same order.
    """
    # We process sequentially to prevent overloading local hardware VRAM.
    # Concurrent requests to a local model require complex queue management.
    entities = []
    for desc in raw_descriptions:
        entities.append(normalize_vendor(desc))
        
    return entities