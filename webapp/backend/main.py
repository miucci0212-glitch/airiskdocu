import os
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor
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
    KrcAssessRequest,
    KrcAssessResponse,
    KrcDownloadRequest,
    KrcExpandRequest,
    KrcRow,
)
from rag.retriever import retrieve_for_request, retrieve_krc
from llm.generator import generate, generate_krc, expand_krc, compute_grade, get_thinking_budget, MODEL_MAP
from excel.writer import fill_template
from excel.krc_writer import fill_krc_template

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
    results: list[KrcSearchItemResult] = []
    with ThreadPoolExecutor(max_workers=min(len(req.items), 8) or 1) as executor:
        futures = [
            executor.submit(
                retrieve_krc,
                detail_work=item.detail_work,
                work_location=item.work_location,
                equipment=item.equipment,
                chroma_dir=settings.krc_chroma_persist_dir,
                top_k=req.top_k,
                use_local_embedding=True,
                gemini_api_key=settings.gemini_api_key,
                collection_name=settings.krc_collection_name,
            )
            for item in req.items
        ]
        all_hits_raw = [f.result() for f in futures]

    for item, hits_raw in zip(req.items, all_hits_raw):
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


@app.post("/api/krc/assess", response_model=KrcAssessResponse)
def krc_assess(req: KrcAssessRequest):
    all_hits_per_item: list[list[dict]] = []
    all_sources: list[KrcRagHit] = []
    with ThreadPoolExecutor(max_workers=min(len(req.items), 8) or 1) as executor:
        futures = [
            executor.submit(
                retrieve_krc,
                detail_work=item.detail_work,
                work_location=item.work_location,
                equipment=item.equipment,
                chroma_dir=settings.krc_chroma_persist_dir,
                top_k=10,
                use_local_embedding=True,
                gemini_api_key=settings.gemini_api_key,
                collection_name=settings.krc_collection_name,
            )
            for item in req.items
        ]
        all_hits_per_item = [f.result() for f in futures]

    for hits in all_hits_per_item:
        if hits:
            top = hits[0]
            all_sources.append(KrcRagHit(
                no=int(top.get("no") or 0),
                project=str(top.get("project") or ""),
                work=str(top.get("work") or ""),
                unit_work=str(top.get("unit_work") or ""),
                sub_work=str(top.get("sub_work") or ""),
                hazard=str(top.get("hazard") or ""),
                accident=str(top.get("accident") or ""),
                controls=str(top.get("controls") or ""),
                laws=str(top.get("laws") or ""),
                permit=str(top.get("permit") or ""),
                distance=float(top.get("distance") or 0.0),
            ))

    default_executor = req.metadata.approver_safety or "작업책임자"
    default_verifier = req.metadata.inspector_supervisor or "공사감독"
    items_dicts = [
        {"detail_work": it.detail_work, "work_location": it.work_location, "equipment": it.equipment}
        for it in req.items
    ]
    generated, _ = generate_krc(
        items=items_dicts,
        rag_hits_per_item=all_hits_per_item,
        api_key=settings.gemini_api_key,
        default_executor=default_executor,
        default_verifier=default_verifier,
        model_override="gemini-2.5-flash",
        generation_mode=req.generation_mode,
    )

    rows: list[KrcRow] = []
    for i, item in enumerate(req.items):
        item_gen_list = generated[3 * i : 3 * i + 3]
        for gen in item_gen_list:
            freq = gen.get("frequency")
            sev = gen.get("severity")
            imp_freq = gen.get("improved_frequency")
            imp_sev = gen.get("improved_severity")
            grade = compute_grade(freq, sev)
            if imp_freq is not None and imp_sev is not None:
                imp_grade = compute_grade(imp_freq, imp_sev)
                improved_risk = f"{imp_freq}/{imp_sev} ({imp_grade})" if imp_grade else f"{imp_freq}/{imp_sev}"
            else:
                improved_risk = ""
            rows.append(KrcRow(
                detail_work=item.detail_work,
                work_location=item.work_location,
                equipment=item.equipment,
                hazard=gen.get("hazard", ""),
                accident_type=gen.get("accident_type", ""),
                frequency=freq,
                severity=sev,
                risk_grade=grade,
                controls=gen.get("controls", ""),
                improved_risk=improved_risk,
                improvement_due="",
                executor="",
                verifier="",
            ))
    return KrcAssessResponse(rows=rows, sources=all_sources)


@app.post("/api/krc/expand", response_model=KrcAssessResponse)
def krc_expand(req: KrcExpandRequest):
    items_dicts = [
        {"detail_work": it.detail_work, "work_location": it.work_location, "equipment": it.equipment}
        for it in req.items
    ]
    existing_hazards = [r.hazard for r in req.existing_rows if r.hazard]

    aggregated_hits: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(req.items), 8) or 1) as executor:
        futures = [
            executor.submit(
                retrieve_krc,
                detail_work=item.detail_work,
                work_location=item.work_location,
                equipment=item.equipment,
                chroma_dir=settings.krc_chroma_persist_dir,
                top_k=15,
                use_local_embedding=True,
                gemini_api_key=settings.gemini_api_key,
                collection_name=settings.krc_collection_name,
            )
            for item in req.items
        ]
        for f in futures:
            aggregated_hits.extend(f.result())

    generated, _ = expand_krc(
        items=items_dicts,
        existing_hazards=existing_hazards,
        count=req.count,
        api_key=settings.gemini_api_key,
        model_override="gemini-2.5-flash",
        rag_hits=aggregated_hits,
        generation_mode=req.generation_mode,
    )

    base = req.existing_rows[-1] if req.existing_rows else None
    base_detail = base.detail_work if base else (req.items[-1].detail_work if req.items else "")
    base_loc = base.work_location if base else (req.items[-1].work_location if req.items else "")
    base_equip = base.equipment if base else (req.items[-1].equipment if req.items else "")

    rows: list[KrcRow] = []
    for gen in generated:
        freq = gen.get("frequency")
        sev = gen.get("severity")
        imp_freq = gen.get("improved_frequency")
        imp_sev = gen.get("improved_severity")
        grade = compute_grade(freq, sev)
        if imp_freq is not None and imp_sev is not None:
            imp_grade = compute_grade(imp_freq, imp_sev)
            improved_risk = f"{imp_freq}/{imp_sev} ({imp_grade})" if imp_grade else f"{imp_freq}/{imp_sev}"
        else:
            improved_risk = ""
        rows.append(KrcRow(
            detail_work=base_detail,
            work_location=base_loc,
            equipment=base_equip,
            hazard=gen.get("hazard", ""),
            accident_type=gen.get("accident_type", ""),
            frequency=freq,
            severity=sev,
            risk_grade=grade,
            controls=gen.get("controls", ""),
            improved_risk=improved_risk,
            improvement_due="",
            executor="",
            verifier="",
        ))
    return KrcAssessResponse(rows=rows, sources=[])


@app.post("/api/krc/download")
def krc_download(req: KrcDownloadRequest):
    tmp_dir = tempfile.mkdtemp()
    site = req.metadata.site_name.replace(" ", "_")[:20] or "현장"
    date_str = req.metadata.write_date.strftime("%Y%m%d")
    suffix = "최초정기" if req.metadata.krc_type == "최초/정기" else "수시"
    filename = f"위험성평가서_{suffix}_{site}_{date_str}.xlsx"
    output_path = os.path.join(tmp_dir, filename)

    template_dir = os.path.dirname(settings.template_xlsx_path)
    fill_krc_template(
        metadata=req.metadata,
        rows=req.rows,
        template_dir=template_dir,
        output_path=output_path,
    )
    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
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
