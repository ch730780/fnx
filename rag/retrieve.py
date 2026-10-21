"""Find the chunks that best answer a question: vector search in Pinecone, then a reranker.

Used by rag/answer.py. Try it from the terminal: python -m rag.retrieve "<question>"
"""
import json
import logging
import sys
from functools import lru_cache

from openai import OpenAI
from pinecone import Pinecone

import config
from rag.prompts import RERANK_PROMPT

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def clients():
    """Connect to OpenAI and Pinecone once per process."""
    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    return OpenAI(api_key=config.OPENAI_API_KEY), pc, pc.Index(config.PINECONE_INDEX)


def rerank(openai_client, question: str, candidates: list[dict]) -> list[dict]:
    """Ask a small model how well each candidate answers the question (0-10), keep the best."""
    chunks = "\n\n".join(f"[{n}] {chunk['text']}" for n, chunk in enumerate(candidates, start=1))
    response = openai_client.chat.completions.create(
        model=config.RERANK_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": RERANK_PROMPT},
            {"role": "user", "content": f"שאלה: {question}\n\nקטעים:\n{chunks}"},
        ],
    )
    scores = json.loads(response.choices[0].message.content)["scores"]   # {"1": 10, "2": 0, ...}
    scored = [{**chunk, "score": scores.get(str(n), 0) / 10} for n, chunk in enumerate(candidates, start=1)]
    return sorted(scored, key=lambda chunk: chunk["score"], reverse=True)[:config.RERANK_TOP_N]


def retrieve(question: str) -> list[dict]:
    """The best chunks for a question, best first, each with a relevance score between 0 and 1."""
    openai_client, pc, index = clients()

    embedding = openai_client.embeddings.create(model=config.EMBEDDING_MODEL, input=question).data[0].embedding
    result = index.query(vector=embedding, top_k=config.TOP_K, include_metadata=True)
    candidates = [{"id": match.id, "score": match.score, **match.metadata} for match in result.matches]
    if not candidates:
        return []
    if not config.USE_RERANKER:
        return candidates[:config.RERANK_TOP_N]

    try:
        return rerank(openai_client, question, candidates)
    except Exception:
        logger.exception("rerank failed - using the vector search order")
        return [{**chunk, "score": 1.0} for chunk in candidates[:config.RERANK_TOP_N]]   # no rerank score: let the answer model judge


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # print Hebrew correctly in the Windows terminal
    for chunk in retrieve(" ".join(sys.argv[1:])):
        print(f"{chunk['score']:.3f}  {chunk['url']}")
        print(f"       {chunk['text'][:150]}")
