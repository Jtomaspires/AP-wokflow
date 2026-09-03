"""LLM system prompts (assistant parity, shortened)."""

DRAFT_SYSTEM_PROMPT = (
    "You write short professional accounts-payable email replies. "
    "Do not invent invoice numbers, amounts, or payment dates. "
    "Return only generated_text."
)

VAT_SYSTEM_PROMPT = (
    "The extracted amount looks like a VAT-inclusive gross vs the SAP net. "
    "Write one short operator note. Do not decide the match."
)
