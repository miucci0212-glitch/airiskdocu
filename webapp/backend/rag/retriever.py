"""ChromaDB에서 위험요인 검색 + 공종 필터링."""
from typing import Optional
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from rag.ingest import COLLECTION_NAME, _get_embedding_function


def _build_query(
    work_description: str,
    equipment: list[str],
    locations: list[str],
) -> str:
    parts = [f"작업내용: {work_description}"]
    if equipment:
        parts.append(f"장비: {', '.join(equipment)}")
    if locations:
        parts.append(f"장소: {', '.join(locations)}")
    return " / ".join(parts)


def retrieve(
    query: str,
    chroma_dir: str,
    top_k: int = 15,
    equipment_keywords: Optional[list[str]] = None,
    use_local_embedding: bool = False,
    gemini_api_key: str = "",
) -> list[dict]:
    client = chromadb.PersistentClient(path=chroma_dir)
    ef = _get_embedding_function(use_local_embedding, gemini_api_key)
    collection = client.get_collection(COLLECTION_NAME, embedding_function=ef)

    count = collection.count()
    if count == 0:
        return []

    raw = collection.query(
        query_texts=[query],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for meta, doc, dist in zip(
        raw["metadatas"][0], raw["documents"][0], raw["distances"][0]
    ):
        results.append({**meta, "document": doc, "distance": dist})

    if equipment_keywords:
        kws = [k.lower() for k in equipment_keywords]

        def score(r):
            text = (r.get("hazard", "") + r.get("control", "") + r.get("work_detail", "")).lower()
            return sum(1 for k in kws if k in text)

        results.sort(key=lambda r: (-score(r), r["distance"]))

    return results[:top_k]


def retrieve_for_request(
    work_description: str,
    equipment: list[str],
    locations: list[str],
    chroma_dir: str,
    top_k: int = 12,
    use_local_embedding: bool = False,
    gemini_api_key: str = "",
) -> list[dict]:
    query = _build_query(work_description, equipment, locations)
    return retrieve(
        query=query,
        chroma_dir=chroma_dir,
        top_k=top_k,
        equipment_keywords=equipment,
        use_local_embedding=use_local_embedding,
        gemini_api_key=gemini_api_key,
    )
