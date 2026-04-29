import os
import tempfile
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from models import AssessRequest, AssessResponse, DownloadRequest, AssessMeta, RagSource
from rag.retriever import retrieve_for_request
from llm.generator import generate, get_thinking_budget, MODEL_MAP
from excel.writer import fill_template

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

app = FastAPI(title="위험성평가 도우미 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    use_local = not settings.gemini_api_key
    rag_results = retrieve_for_request(
        work_description=req.work_description,
        equipment=req.equipment,
        locations=req.locations,
        chroma_dir=settings.chroma_persist_dir,
        top_k=12,
        use_local_embedding=use_local,
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
    )

    sources = [
        RagSource(sheet=r["sheet"], row_id=r["row_id"], hazard_snippet=r["hazard"][:50])
        for r in rag_results[:5]
    ]
    budget = get_thinking_budget(req.thinking_level)
    model = MODEL_MAP.get(req.thinking_level, settings.gemini_generation_model)

    return AssessResponse(
        rows=rows,
        sources=sources,
        meta=AssessMeta(model=model, thinking_budget=budget, fallback_used=fallback),
    )


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
