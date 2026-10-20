"""Turn every chunk into an embedding (OpenAI) and store it in the Pinecone index.

Run: python -m pipeline.index
Reads data/chunks.jsonl (made by chunk.py). Creates the index on the first run.
Safe to re-run: a chunk with an id that already exists is overwritten (upsert).
"""
import json
from pathlib import Path

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

import config

CHUNKS_PATH = Path("data/chunks.jsonl")   # input: chunks made by chunk.py
EMBED_BATCH = 100                         # chunks sent to OpenAI in one request
UPSERT_BATCH = 20                         # vectors sent to Pinecone in one request (each request must stay under 2MB)


def get_index(pc: Pinecone):
    """Open our Pinecone index, creating it first if it does not exist yet."""
    if not pc.has_index(config.PINECONE_INDEX):
        pc.create_index(
            name=config.PINECONE_INDEX,
            dimension=config.EMBEDDING_DIM,                        # must match the embedding model (3072)
            metric="cosine",                                       # similarity = angle between two vectors
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),  # the region of Pinecone's free plan
        )
    return pc.Index(config.PINECONE_INDEX)


def upload(chunks: list[dict], openai_client: OpenAI, index) -> None:
    """Embed the chunks (OpenAI) and store them in Pinecone, in batches."""
    for start in tqdm(range(0, len(chunks), EMBED_BATCH)):
        batch = chunks[start:start + EMBED_BATCH]
        response = openai_client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=[chunk["text"] for chunk in batch],
        )
        vectors = [
            {
                "id": chunk["id"],
                "values": item.embedding,                                           # 3072 numbers = the meaning of the text
                "metadata": {key: value for key, value in chunk.items() if key != "id"},  # url, title, text... returned with every match
            }
            for chunk, item in zip(batch, response.data)
        ]
        index.upsert(vectors=vectors, batch_size=UPSERT_BATCH, show_progress=False)


def main() -> None:
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]

    index = get_index(Pinecone(api_key=config.PINECONE_API_KEY))
    upload(chunks, OpenAI(api_key=config.OPENAI_API_KEY), index)

    stats = index.describe_index_stats()
    print(f"chunks sent: {len(chunks)}  |  vectors in index: {stats.total_vector_count}")


if __name__ == "__main__":
    main()
