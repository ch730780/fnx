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
CHAT_MODEL = ""                # chosen after checking which models the account can access
REWRITE_MODEL = ""             # small model for rewriting follow-up questions

# Pinecone
PINECONE_INDEX = "fnx"

# Retrieval
TOP_K = 20                     # candidates from the first search
RERANK_TOP_N = 5               # kept after reranking
MIN_RELEVANCE = 0.3            # below this the bot refuses; tuned from eval results
