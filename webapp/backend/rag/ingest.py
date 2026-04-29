"""위험성평가 XLSX → ChromaDB 인덱싱."""
import os
import hashlib
import pandas as pd
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


COLLECTION_NAME = "risk_db"


def build_document_text(trade: str, work_detail: str, hazard: str, control: str) -> str:
    return (
        f"[공종]{trade} "
        f"[세부작업]{work_detail} "
        f"[위험요인]{hazard} "
        f"[대책]{control}"
    )


def _make_id(trade: str, row_idx: int) -> str:
    return hashlib.md5(f"{trade}|row{row_idx}".encode()).hexdigest()


def _get_embedding_function(use_local: bool, api_key: str = ""):
    if use_local or not api_key:
        return DefaultEmbeddingFunction()
    import google.generativeai as genai

    class GeminiEmbedding:
        def __call__(self, input):  # noqa: A002
            genai.configure(api_key=api_key)
            results = []
            for text in input:
                r = genai.embed_content(model="models/text-embedding-004", content=text)
                results.append(r["embedding"])
            return results

    return GeminiEmbedding()


def ingest(
    xlsx_path: str,
    chroma_dir: str,
    use_local_embedding: bool = False,
    gemini_api_key: str = "",
    force: bool = False,
) -> int:
    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    ef = _get_embedding_function(use_local_embedding, gemini_api_key)

    try:
        if force:
            client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        COLLECTION_NAME, embedding_function=ef
    )

    xl = pd.ExcelFile(xlsx_path)
    total = 0
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        if df.empty:
            continue
        for row_idx, row in df.iterrows():
            trade = str(row.get("공종", sheet_name)).strip()
            work_detail = str(row.get("세부작업", "")).strip()
            hazard = str(row.get("위험요인", "")).strip()
            control = str(row.get("안전대책", "")).strip()
            if not hazard or hazard == "nan":
                continue
            doc_text = build_document_text(trade, work_detail, hazard, control)
            doc_id = _make_id(trade, int(str(row_idx)))
            collection.upsert(
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[{
                    "trade": trade,
                    "work_detail": work_detail,
                    "hazard": hazard,
                    "control": control,
                    "disaster_type": str(row.get("재해형태", "")).strip(),
                    "sheet": sheet_name,
                    "row_id": f"{sheet_name}|row{row_idx}",
                }],
            )
            total += 1

    print(f"인덱싱 완료: {total}건")
    return total


if __name__ == "__main__":
    import sys
    from config import settings

    xlsx = sys.argv[1] if len(sys.argv) > 1 else settings.source_xlsx_path
    chroma = sys.argv[2] if len(sys.argv) > 2 else settings.chroma_persist_dir
    force = "--force" in sys.argv
    ingest(
        xlsx_path=xlsx,
        chroma_dir=chroma,
        use_local_embedding=not settings.gemini_api_key,
        gemini_api_key=settings.gemini_api_key,
        force=force,
    )
