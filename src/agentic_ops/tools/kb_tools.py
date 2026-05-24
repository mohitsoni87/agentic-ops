from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from ..config import settings
from ..db.connection import get_session

_embeddings: OpenAIEmbeddings | None = None


def get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key,
        )
    return _embeddings


def _vec_str(embedding: list[float]) -> str:
    return f"[{','.join(str(x) for x in embedding)}]"


@tool
async def search_known_errors(query_text: str, top_k: int = 3) -> list[dict]:
    """Search the known_errors knowledge base using semantic similarity on log/error text."""
    embedding = await get_embeddings().aembed_query(query_text)
    emb_str = _vec_str(embedding)
    async with get_session() as session:
        rows = await session.execute(
            text("""
                SELECT id, error_type, pattern, log_keywords,
                       1 - (embedding <=> :emb::vector) AS similarity
                FROM known_errors
                ORDER BY embedding <=> :emb::vector
                LIMIT :k
            """),
            {"emb": emb_str, "k": top_k},
        )
        return [dict(r._mapping) for r in rows]


@tool
async def get_error_root_causes(known_error_id: int) -> list[dict]:
    """Fetch all root causes linked to a known error ID."""
    async with get_session() as session:
        rows = await session.execute(
            text("SELECT id, description FROM root_causes WHERE known_error_id = :eid"),
            {"eid": known_error_id},
        )
        return [dict(r._mapping) for r in rows]


@tool
async def search_solutions(query_text: str, top_k: int = 3) -> list[dict]:
    """Search the solutions knowledge base using semantic similarity on root cause text."""
    embedding = await get_embeddings().aembed_query(query_text)
    emb_str = _vec_str(embedding)
    async with get_session() as session:
        rows = await session.execute(
            text("""
                SELECT s.id, s.title, s.description, s.steps,
                       1 - (s.embedding <=> :emb::vector) AS similarity
                FROM solutions s
                ORDER BY s.embedding <=> :emb::vector
                LIMIT :k
            """),
            {"emb": emb_str, "k": top_k},
        )
        return [dict(r._mapping) for r in rows]
