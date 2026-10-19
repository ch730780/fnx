"""Find the chunks that best answer a question: vector search in Pinecone, then a reranker.

Used by rag/answer.py. Try it from the terminal: python -m rag.retrieve "<question>"
"""
import sys
from functools import lru_cache

from openai import OpenAI
from pinecone import Pinecone

import config

RERANK_MODEL = "bge-reranker-v2-m3"   # Pinecone's hosted multilingual reranker


@lru_cache(maxsize=1)
def clients():
    """Connect to OpenAI and Pinecone once per process."""
    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    return OpenAI(api_key=config.OPENAI_API_KEY), pc, pc.Index(config.PINECONE_INDEX)


def retrieve(question: str) -> list[dict]:
    """The best chunks for a question, best first, each with a relevance score between 0 and 1."""
    openai_client, pc, index = clients()

    embedding = openai_client.embeddings.create(model=config.EMBEDDING_MODEL, input=question).data[0].embedding
    result = index.query(vector=embedding, top_k=config.TOP_K, include_metadata=True)
    candidates = [{"id": match.id, **match.metadata} for match in result.matches]
    if not candidates:
        return []

    reranked = pc.inference.rerank(
        model=RERANK_MODEL,
        query=question,
        documents=[chunk["text"] for chunk in candidates],
        top_n=config.RERANK_TOP_N,
        return_documents=False,
        parameters={"truncate": "END"},   # a chunk longer than the model's limit is cut, not rejected
    )
    return [{**candidates[row.index], "score": row.score} for row in reranked.data]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # print Hebrew correctly in the Windows terminal
    for chunk in retrieve(" ".join(sys.argv[1:])):
        print(f"{chunk['score']:.3f}  {chunk['url']}")
        print(f"       {chunk['text'][:150]}")
