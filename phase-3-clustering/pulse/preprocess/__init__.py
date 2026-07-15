"""Preprocessing & safety layer (architecture §3.2 `scrub_pii`, §11).

PII scrubbing and language detection. PII is removed before embeddings, the LLM, and any
published output; reviews are treated as data, never instructions.
"""
