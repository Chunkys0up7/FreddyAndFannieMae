"""Embedding helpers — actual embedding happens inside the Chroma collection."""
from __future__ import annotations

# The ChromaVectorStore wires sentence-transformers (or OpenAI) directly into
# the collection's embedding_function. This file exists for API symmetry with
# the spec layout and to host any future custom embedding flows.
