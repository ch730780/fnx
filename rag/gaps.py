"""Content gaps: questions the website does not answer, saved for the content team.

answer.py saves them after a "not on the site" reply; app.py shows them grouped by meaning (?view=gaps).
"""
import logging
import uuid
from datetime import date

import config
from rag.retrieve import clients

SIMILAR = 0.75  # measured: rewordings 0.70-0.93; same-template prices of other products 0.71-0.72 (car vs cat), so 0.68 joined them

logger = logging.getLogger(__name__)


def save_gap(question: str, meaning: str) -> None:
    """Store one unanswered question as the user typed it, with the meaning vector of its full (rewritten) form.

    The full form groups follow-ups like "and for cats?" correctly. Never raises: the user already got the answer.
    """
    question = question.strip().strip('"\'״“”').strip()   # pasted questions often come with quotes or blank lines
    try:
        openai_client, _, index = clients()
        vector = openai_client.embeddings.create(model=config.EMBEDDING_MODEL, input=meaning).data[0].embedding
        index.upsert(vectors=[{"id": str(uuid.uuid4()), "values": vector,
                               "metadata": {"question": question, "date": date.today().isoformat()}}],
                     namespace=config.GAPS_NAMESPACE)
    except Exception:
        logger.exception("saving a content gap failed")


def similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))   # cosine (vectors are normalized)


def load_groups() -> list[dict]:
    """All saved questions, grouped by meaning, the most asked first.

    Each question joins the group it is most similar to. A group's title is its most typical question
    (the one closest to all the others), so it stays the same however Pinecone orders the records.
    """
    _, _, index = clients()
    groups = []
    for page in index.list(namespace=config.GAPS_NAMESPACE):
        fetched = index.fetch(ids=[item.id for item in page.vectors], namespace=config.GAPS_NAMESPACE)
        for record in fetched.vectors.values():
            best = max(groups, key=lambda group: similarity(group["vector"], record.values), default=None)
            if best and similarity(best["vector"], record.values) >= SIMILAR:
                best["records"].append(record)
            else:
                groups.append({"vector": record.values, "records": [record]})
    for group in groups:
        records = group["records"]
        typical = max(records, key=lambda record: sum(similarity(record.values, other.values) for other in records))
        group["title"] = typical.metadata["question"]
        group["questions"] = [record.metadata for record in records]
    return sorted(groups, key=lambda group: len(group["questions"]), reverse=True)
