"""ChromaDB에서 위험요인 검색 + 공종 필터링."""
import threading
from typing import Optional
import chromadb

from rag.ingest import COLLECTION_NAME, KRC_COLLECTION_NAME, _get_embedding_function

_cache_lock = threading.Lock()
_client_cache = {}
_ef_cache = {}
_collection_cache = {}


def _get_cached_collection(
    chroma_dir: str,
    collection_name: str,
    use_local_embedding: bool,
    gemini_api_key: str,
):
    key = (chroma_dir, collection_name, use_local_embedding, gemini_api_key)
    with _cache_lock:
        if key in _collection_cache:
            return _collection_cache[key]

        if chroma_dir not in _client_cache:
            _client_cache[chroma_dir] = chromadb.PersistentClient(path=chroma_dir)
        client = _client_cache[chroma_dir]

        ef_key = (use_local_embedding, gemini_api_key)
        if ef_key not in _ef_cache:
            _ef_cache[ef_key] = _get_embedding_function(use_local_embedding, gemini_api_key)
        ef = _ef_cache[ef_key]

        collection = client.get_collection(collection_name, embedding_function=ef)
        _collection_cache[key] = collection
        return collection


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
    collection_name: str = COLLECTION_NAME,
) -> list[dict]:
    collection = _get_cached_collection(
        chroma_dir=chroma_dir,
        collection_name=collection_name,
        use_local_embedding=use_local_embedding,
        gemini_api_key=gemini_api_key,
    )

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


def retrieve_krc(
    detail_work: str,
    work_location: str,
    equipment: str,
    chroma_dir: str,
    top_k: int = 8,
    use_local_embedding: bool = True,
    gemini_api_key: str = "",
    collection_name: str = KRC_COLLECTION_NAME,
) -> list[dict]:
    """농어촌공사 KRC 컬렉션에서 항목(단위작업/작업위치/사용장비) 기반 RAG 검색."""
    parts = []
    if detail_work:
        parts.append(f"단위작업: {detail_work}")
    if work_location:
        parts.append(f"작업위치: {work_location}")
    if equipment:
        parts.append(f"사용장비/설비/인원: {equipment}")
    query = " / ".join(parts) or detail_work
    equipment_kws = [s.strip() for s in equipment.split(",") if s.strip()] if equipment else None

    collection = _get_cached_collection(
        chroma_dir=chroma_dir,
        collection_name=collection_name,
        use_local_embedding=use_local_embedding,
        gemini_api_key=gemini_api_key,
    )

    count = collection.count()
    if count == 0:
        return []

    raw = collection.query(
        query_texts=[query],
        n_results=min(top_k * 2, count),
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for meta, doc, dist in zip(
        raw["metadatas"][0], raw["documents"][0], raw["distances"][0]
    ):
        results.append({**meta, "document": doc, "distance": dist})

    if equipment_kws:
        kws = [k.lower() for k in equipment_kws]

        def score(r):
            text = (
                r.get("hazard", "") + r.get("controls", "") + r.get("sub_work", "")
            ).lower()
            return sum(1 for k in kws if k in text)

        results.sort(key=lambda r: (-score(r), r["distance"]))

    return results[:top_k]
