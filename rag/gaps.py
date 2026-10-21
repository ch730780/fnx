"""Content gaps: questions the website does not answer, saved for the content team.

answer.py saves them after a "not on the site" reply; app.py shows them grouped by meaning (?view=gaps).
"""
import logging
import uuid
from datetime import date

import config
from rag.retrieve import clients

SIMILAR = 0.68  # measured: rewordings of one question 0.70-0.91; different topics 0.62 or less (cat vs dog price up to 0.79 may join)

logger = logging.getLogger(__name__)


def save_gap(question: str) -> None:
    """Store one unanswered question with its meaning vector. Never raises: the user already got the answer."""
    question = question.strip().strip('"\'״“”').strip()   # pasted questions often come with quotes or blank lines
    try:
        openai_client, _, index = clients()
        vector = openai_client.embeddings.create(model=config.EMBEDDING_MODEL, input=question).data[0].embedding
        index.upsert(vectors=[{"id": str(uuid.uuid4()), "values": vector,
                               "metadata": {"question": question, "date": date.today().isoformat()}}],
                     namespace=config.GAPS_NAMESPACE)
    except Exception:
        logger.exception("saving a content gap failed")


def load_groups() -> list[dict]:
    """All saved questions, grouped by meaning, the most asked first."""
    _, _, index = clients()
    groups = []
    for page in index.list(namespace=config.GAPS_NAMESPACE):
        fetched = index.fetch(ids=[item.id for item in page.vectors], namespace=config.GAPS_NAMESPACE)
        for record in fetched.vectors.values():
            for group in groups:
                if sum(a * b for a, b in zip(group["vector"], record.values)) >= SIMILAR:   # cosine (vectors are normalized)
                    group["questions"].append(record.metadata)
                    break
            else:
                groups.append({"vector": record.values, "questions": [record.metadata]})
    return sorted(groups, key=lambda group: len(group["questions"]), reverse=True)
