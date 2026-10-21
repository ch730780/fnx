import os

from dotenv import load_dotenv

try:
    import truststore
    truststore.inject_into_ssl()   # use the Windows certificate store (needed behind a TLS-inspecting filter)
except ImportError:
    pass                           # not installed (e.g. in the cloud) - default certificates are fine

load_dotenv()  # locally: reads .env; in the cloud: no-op

# API keys: read from environment variables (works locally, on Streamlit Cloud and on AWS)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Site
BASE_URL = "https://www.fnx.co.il"
CRAWL_DELAY_SEC = 1.5          # delay between requests (polite crawling)
USER_AGENT = "Mozilla/5.0 (compatible; FnxRagBot/0.1; hackathon RAG project)"
EXCLUDED_SECTIONS = ["en", "tags", "404", "sitemap"]   # site sections we don't crawl

# Models
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
CHAT_MODEL = "gpt-4.1"         # writes the answer: follows instructions well, fast, supports JSON output
REWRITE_MODEL = "gpt-4.1-mini" # small and fast: rewrites follow-up questions into full questions
FALLBACK_MODEL = "gpt-4.1-mini" # used only if CHAT_MODEL fails (error 429, outage)
RERANK_MODEL = "gpt-4.1-mini"  # scores how well each found chunk answers the question (0-10)

# Pinecone
PINECONE_INDEX = "fnx"

# Retrieval
TOP_K = 20                     # candidates from the first search
RERANK_TOP_N = 5               # kept after reranking
USE_RERANKER = True            # False = keep the vector search order (faster, usually less precise)
MIN_RELEVANCE = 0.5            # chunks below this reranker score are dropped; measured on 47 eval questions:
                               # answerable questions scored 0.9+, same topic but not the answer 0.6-0.7,
                               # unrelated 0.3 or less - 0.5 keeps related info for the "what the site does say" card
