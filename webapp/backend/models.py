from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Period(BaseModel):
    start: date
    end: date


class AssessRequest(BaseModel):
    site_name: str = Field(..., description="현장명")
    vendor: str = Field(..., description="업체명")
    trade: str = Field(..., description="공종")
    period: Period
    headcount: int = Field(..., ge=1)
    leader: str = Field(..., description="작업 책임자 이름")
    workers: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list, description="기계/기구/위험물질")
    machinery: str = Field(default="해당없음", description="건설기계 종류 및 댓 수")
    locations: list[str] = Field(..., description="작업장소 목록")
    work_description: str = Field(..., description="작업내용 자연어 기술")
    thinking_level: Literal["fast", "balanced", "thorough", "max"] = "balanced"
    model_override: Optional[str] = None


class AssessRow(BaseModel):
    location: str
    work: str
    hazard: str
    control: str
    note: str = ""


class RagSource(BaseModel):
    sheet: str
    row_id: str
    hazard_snippet: str


class AssessMeta(BaseModel):
    model: str
    thinking_budget: int
    fallback_used: bool


class AssessResponse(BaseModel):
    rows: list[AssessRow]
    sources: list[RagSource]
    meta: AssessMeta


class DownloadRequest(BaseModel):
    request: AssessRequest
    rows: list[AssessRow]


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: str = ""


class ErrorResponse(BaseModel):
    error: ErrorDetail


class KrcSearchItem(BaseModel):
    detail_work: str = Field("", description="세부작업(단위작업)")
    work_location: str = Field("", description="작업위치")
    equipment: str = Field("", description="사용장비/설비/인원")


class KrcSearchRequest(BaseModel):
    items: list[KrcSearchItem]
    top_k: int = Field(8, ge=1, le=30)


class KrcRagHit(BaseModel):
    no: int = 0
    project: str = ""
    work: str = ""
    unit_work: str = ""
    sub_work: str = ""
    hazard: str = ""
    accident: str = ""
    controls: str = ""
    laws: str = ""
    permit: str = ""
    distance: float = 0.0


class KrcSearchItemResult(BaseModel):
    query: KrcSearchItem
    hits: list[KrcRagHit]


class KrcSearchResponse(BaseModel):
    results: list[KrcSearchItemResult]
