import os
import tempfile
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from models import (
    AssessRequest,
    AssessResponse,
    DownloadRequest,
    AssessMeta,
    RagSource,
    KrcSearchRequest,
    KrcSearchResponse,
    KrcSearchItemResult,
    KrcRagHit,
)
from rag.retriever import retrieve_for_request, retrieve_krc
from llm.generator import generate, get_thinking_budget, MODEL_MAP
from excel.writer import fill_template

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

app = FastAPI(title="위험성평가 도우미 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    rag_results = retrieve_for_request(
        work_description=req.work_description,
        equipment=req.equipment,
        locations=req.locations,
        chroma_dir=settings.chroma_persist_dir,
        top_k=12,
        use_local_embedding=True,
        gemini_api_key=settings.gemini_api_key,
    )

    if not rag_results:
        raise HTTPException(
            status_code=422,
            detail={"code": "RAG_NO_MATCH", "message": "관련 위험요인을 찾을 수 없습니다."}
        )

    rows, fallback = generate(
        work_description=req.work_description,
        equipment=req.equipment,
        locations=req.locations,
        rag_results=rag_results,
        api_key=settings.gemini_api_key,
        thinking_level=req.thinking_level,
        timeout=settings.llm_timeout_sec,
        model_override=req.model_override,
    )

    sources = [
        RagSource(sheet=r["sheet"], row_id=r["row_id"], hazard_snippet=r["hazard"][:50])
        for r in rag_results[:5]
    ]
    budget = get_thinking_budget(req.thinking_level)
    model = req.model_override or MODEL_MAP.get(req.thinking_level, settings.gemini_generation_model)

    return AssessResponse(
        rows=rows,
        sources=sources,
        meta=AssessMeta(model=model, thinking_budget=budget, fallback_used=fallback),
    )


@app.post("/api/krc/search", response_model=KrcSearchResponse)
def krc_search(req: KrcSearchRequest):
    use_local = not settings.gemini_api_key
    results: list[KrcSearchItemResult] = []
    for item in req.items:
        hits_raw = retrieve_krc(
            detail_work=item.detail_work,
            work_location=item.work_location,
            equipment=item.equipment,
            chroma_dir=settings.chroma_persist_dir,
            top_k=req.top_k,
            use_local_embedding=use_local,
            gemini_api_key=settings.gemini_api_key,
            collection_name=settings.krc_collection_name,
        )
        hits = [
            KrcRagHit(
                no=int(h.get("no") or 0),
                project=str(h.get("project") or ""),
                work=str(h.get("work") or ""),
                unit_work=str(h.get("unit_work") or ""),
                sub_work=str(h.get("sub_work") or ""),
                hazard=str(h.get("hazard") or ""),
                accident=str(h.get("accident") or ""),
                controls=str(h.get("controls") or ""),
                laws=str(h.get("laws") or ""),
                permit=str(h.get("permit") or ""),
                distance=float(h.get("distance") or 0.0),
            )
            for h in hits_raw
        ]
        results.append(KrcSearchItemResult(query=item, hits=hits))
    return KrcSearchResponse(results=results)


@app.post("/api/download")
def download(req: DownloadRequest):
    tmp_dir = tempfile.mkdtemp()
    site = req.request.site_name.replace(" ", "_")[:20]
    date_str = req.request.period.start.strftime("%Y%m%d")
    filename = f"위험성평가서_{site}_{date_str}.xlsx"
    output_path = os.path.join(tmp_dir, filename)

    fill_template(
        request=req.request,
        rows=req.rows,
        template_path=settings.template_xlsx_path,
        output_path=output_path,
        cell_map_path=settings.cell_map_path,
    )

    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )
