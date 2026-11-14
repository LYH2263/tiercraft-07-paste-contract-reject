from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import pipeline

router = APIRouter(tags=["主题域"])


class ContractField(BaseModel):
    field: str = Field(..., description="源字段名")
    required: bool = Field(default=True, description="是否必填")
    ftype: str = Field(..., description="字段类型：文本/数值/整数/日期")


class ContractBody(BaseModel):
    fields: list[ContractField] = Field(..., description="期望字段契约")


@router.get("/domains")
def list_domains():
    return pipeline.list_domains()


@router.get("/domains/{domain_id}")
def get_domain(domain_id: int):
    d = pipeline.get_domain(domain_id)
    if not d:
        raise HTTPException(status_code=404, detail="主题域不存在")
    return d


@router.get("/domains/{domain_id}/contract")
def get_contract(domain_id: int):
    if not pipeline.get_domain(domain_id):
        raise HTTPException(status_code=404, detail="主题域不存在")
    return {
        "domain_id": domain_id,
        "fields": pipeline.get_contract(domain_id),
        "types": pipeline.CONTRACT_TYPES,
    }


@router.put("/domains/{domain_id}/contract")
def save_contract(domain_id: int, body: ContractBody):
    try:
        fields = pipeline.save_contract(domain_id, [f.model_dump() for f in body.fields])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"domain_id": domain_id, "fields": fields, "types": pipeline.CONTRACT_TYPES}


@router.get("/domains/{domain_id}/rejects")
def list_rejects(domain_id: int):
    if not pipeline.get_domain(domain_id):
        raise HTTPException(status_code=404, detail="主题域不存在")
    return pipeline.list_rejects(domain_id)
