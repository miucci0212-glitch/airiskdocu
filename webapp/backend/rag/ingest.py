"""위험성평가 XLSX → ChromaDB 인덱싱."""
import os

# macOS CoreML 실행 프로바이더가 가끔 모델 추론에서 실패하므로
# chromadb가 onnxruntime을 로드하기 전에 CPU 프로바이더만 쓰도록 강제한다.
try:
    import onnxruntime as _ort

    _orig_session = _ort.InferenceSession

    def _cpu_only_session(*args, **kwargs):
        kwargs["providers"] = ["CPUExecutionProvider"]
        return _orig_session(*args, **kwargs)

    _ort.InferenceSession = _cpu_only_session
except ImportError:
    pass

import hashlib
import pandas as pd
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


COLLECTION_NAME = "risk_db"
KRC_COLLECTION_NAME = "krc_db"


def build_document_text(trade: str, work_detail: str, hazard: str, control: str) -> str:
    return (
        f"[공종]{trade} "
        f"[세부작업]{work_detail} "
        f"[위험요인]{hazard} "
        f"[대책]{control}"
    )


def _make_id(sheet_name: str, trade: str, row_idx: int, source: str = "") -> str:
    return hashlib.md5(
        f"{source}|{sheet_name}|{trade}|row{row_idx}".encode()
    ).hexdigest()


def _get_embedding_function(use_local: bool, api_key: str = "", model_name: str = ""):
    if use_local or not api_key:
        return DefaultEmbeddingFunction()
    import time
    import google.generativeai as genai

    # 모델명 정규화: 'models/' 접두 없으면 자동 부여
    if not model_name:
        from config import settings as _s
        model_name = _s.gemini_embedding_model
    model = model_name if model_name.startswith("models/") else f"models/{model_name}"

    class GeminiEmbedding:
        # Gemini 임베딩 batch 한도는 100. 안전하게 100씩 끊어서 호출한다.
        BATCH = 100
        # Free tier 한도가 분당 100 요청이지만 burst 보호가 빡빡해서 40 RPM(1.5s 간격)으로 페이싱.
        MIN_INTERVAL = 1.5

        def __init__(self):
            genai.configure(api_key=api_key)
            self._last_call = 0.0

        def __call__(self, input):  # noqa: A002
            if not isinstance(input, list):
                input = [input]
            results: list[list[float]] = []
            for i in range(0, len(input), self.BATCH):
                chunk = input[i : i + self.BATCH]
                # 요청간 최소 간격 유지
                wait = self.MIN_INTERVAL - (time.time() - self._last_call)
                if wait > 0:
                    time.sleep(wait)
                # 429 발생 시 1분 윈도우가 리셋되도록 백오프, 반복되면 throttle 영구 증가
                for attempt in range(6):
                    try:
                        r = genai.embed_content(model=model, content=chunk)
                        break
                    except Exception as e:
                        msg = str(e)
                        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                            backoff = min(30 * (2 ** attempt), 240)  # 30, 60, 120, 240, ...
                            print(f"[throttle] 429 hit (attempt {attempt+1}), sleeping {backoff}s, MIN_INTERVAL={self.MIN_INTERVAL}", flush=True)
                            time.sleep(backoff)
                            # 영구 throttle 강화 (1.5x 씩, 최대 5초)
                            self.MIN_INTERVAL = min(self.MIN_INTERVAL * 1.5, 5.0)
                            continue
                        raise
                else:
                    raise RuntimeError("Gemini embedding: 6번 재시도 후 실패")
                self._last_call = time.time()
                emb = r["embedding"]
                # 단일 요청이면 embedding 이 1차원 리스트, 배치면 2차원 리스트
                if emb and isinstance(emb[0], (int, float)):
                    results.append(emb)
                else:
                    results.extend(emb)
            return results

    return GeminiEmbedding()


def ingest(
    xlsx_path: str,
    chroma_dir: str,
    use_local_embedding: bool = False,
    gemini_api_key: str = "",
    force: bool = False,
    source: str = "guideline",
) -> int:
    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    ef = _get_embedding_function(use_local_embedding, gemini_api_key)

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except ValueError:
            pass  # collection did not exist yet

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
            doc_id = _make_id(sheet_name, trade, int(str(row_idx)), source)
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
                    "row_id": f"{source}|{sheet_name}|row{row_idx}",
                    "source": source,
                }],
            )
            total += 1

    print(f"인덱싱 완료: {total}건")
    return total


def _krc_doc_text(unit_work: str, sub_work: str, hazard: str, accident: str) -> str:
    return (
        f"[단위작업]{unit_work} "
        f"[세부단위작업]{sub_work} "
        f"[유해위험요인]{hazard} "
        f"[재해유형]{accident}"
    )


def ingest_krc(
    xlsx_path: str,
    chroma_dir: str,
    collection_name: str = KRC_COLLECTION_NAME,
    use_local_embedding: bool = True,
    gemini_api_key: str = "",
    force: bool = False,
    batch_size: int = 100,
) -> int:
    """농어촌공사 자체 유해·위험요인 DB 인제스트.

    원본 시트는 No. 컬럼이 숫자인 행이 새 위험요인을 시작하고, No.='-' 행은
    같은 위험요인에 대한 추가 감소대책 행이다. 같은 그룹의 감소대책을 합쳐
    한 그룹당 한 도큐먼트로 색인한다.
    """
    import openpyxl

    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    ef = _get_embedding_function(use_local_embedding, gemini_api_key)

    if force:
        try:
            client.delete_collection(collection_name)
        except ValueError:
            pass

    collection = client.get_or_create_collection(collection_name, embedding_function=ef)

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb.active

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    seen_ids: set[str] = set()

    def flush():
        nonlocal ids, docs, metas
        if not ids:
            return
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        print(f"  [krc] flushed batch, total so far = {total}", flush=True)
        ids, docs, metas = [], [], []

    current_no: int | None = None
    current: dict | None = None
    total = 0

    def emit(group: dict):
        nonlocal total
        # ID 키에 사업/공사/단위/세부단위까지 포함해야 다른 섹션의 동일 No.+위험요인 충돌을 피한다.
        key = "|".join([
            "krc",
            group["project"], group["work"], group["unit_work"], group["sub_work"],
            str(group["no"]), group["hazard"], group["accident"],
        ])
        doc_id = hashlib.md5(key.encode()).hexdigest()
        if doc_id in seen_ids:
            return  # 진짜 중복(완전 동일 행): 스킵
        seen_ids.add(doc_id)
        controls_joined = " | ".join([c for c in group["controls"] if c])
        doc_text = _krc_doc_text(
            group["unit_work"], group["sub_work"], group["hazard"], group["accident"]
        )
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append({
            "no": group["no"],
            "project": group["project"],
            "work": group["work"],
            "unit_work": group["unit_work"],
            "sub_work": group["sub_work"],
            "hazard": group["hazard"],
            "accident": group["accident"],
            "controls": controls_joined,
            "laws": group["laws"],
            "permit": group["permit"],
            "source": "krc",
        })
        total += 1
        if len(ids) >= batch_size:
            flush()

    for raw in ws.iter_rows(min_row=4, values_only=True):
        no_cell = raw[0]
        if no_cell is None and not any(raw):
            continue
        is_new = isinstance(no_cell, (int, float))
        if is_new:
            if current is not None:
                emit(current)
            current_no = int(no_cell)
            current = {
                "no": current_no,
                "project": str(raw[1] or "").strip(),
                "work": str(raw[2] or "").strip(),
                "unit_work": str(raw[3] or "").strip(),
                "sub_work": str(raw[4] or "").strip(),
                "hazard": str(raw[5] or "").strip(),
                "accident": str(raw[6] or "").strip(),
                "controls": [str(raw[7] or "").strip()],
                "laws": str(raw[8] or "").strip(),
                "permit": str(raw[9] or "").strip(),
            }
        else:
            if current is None:
                continue  # leading "-" before any numbered row — skip
            extra = str(raw[7] or "").strip()
            if extra:
                current["controls"].append(extra)

    if current is not None:
        emit(current)

    flush()
    print(f"KRC 인덱싱 완료: {total}건 → 컬렉션 '{collection_name}'")
    return total


if __name__ == "__main__":
    import sys
    from config import settings

    if "--krc" in sys.argv:
        force = "--force" in sys.argv
        xlsx = settings.krc_source_xlsx_path
        for i, a in enumerate(sys.argv):
            if a == "--xlsx" and i + 1 < len(sys.argv):
                xlsx = sys.argv[i + 1]
        ingest_krc(
            xlsx_path=xlsx,
            chroma_dir=settings.chroma_persist_dir,
            collection_name=settings.krc_collection_name,
            use_local_embedding=not settings.gemini_api_key,
            gemini_api_key=settings.gemini_api_key,
            force=force,
        )
    else:
        xlsx = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else settings.source_xlsx_path
        chroma = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else settings.chroma_persist_dir
        force = "--force" in sys.argv
        source = "guideline"
        for a in sys.argv:
            if a.startswith("--source="):
                source = a.split("=", 1)[1]
        ingest(
            xlsx_path=xlsx,
            chroma_dir=chroma,
            use_local_embedding=not settings.gemini_api_key,
            gemini_api_key=settings.gemini_api_key,
            force=force,
            source=source,
        )
