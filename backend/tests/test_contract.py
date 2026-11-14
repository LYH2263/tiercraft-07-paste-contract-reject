import os
import tempfile
from pathlib import Path

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="tiercraft-test-"))
os.environ.setdefault(
    "FIXTURES_DIR", str(Path(__file__).resolve().parents[2] / "fixtures")
)

import pytest

from app import seed
from app.services import pipeline


@pytest.fixture(scope="module", autouse=True)
def _init():
    seed.init_db()


@pytest.fixture(autouse=True)
def _reset_contract():
    pipeline.save_contract(1, pipeline.DEFAULT_CONTRACT)
    pipeline.run_load_paste(1)
    yield


def test_default_contract_covers_required_fields():
    fields = pipeline.get_contract(1)
    by_name = {f["field"]: f for f in fields}
    for name in ["业务日", "门店编码", "门店名称", "品类", "金额", "件数"]:
        assert name in by_name
        assert by_name[name]["required"] is True
    assert by_name["金额"]["ftype"] == "数值"
    assert by_name["件数"]["ftype"] == "整数"
    assert by_name["业务日"]["ftype"] == "日期"


def test_load_report_matches_paste_and_rejects():
    job = pipeline.run_load_paste(1)
    counts = pipeline.layer_counts(1)
    rejects = pipeline.list_rejects(1)
    assert job["out_count"] == counts["贴源层"] == 6
    assert job["drop_count"] == len(rejects) == 4
    assert job["in_count"] == job["out_count"] + job["drop_count"]


def test_reject_reasons_and_raw_line_kept():
    rejects = {r["line_no"]: r for r in pipeline.list_rejects(1)}
    assert "门店名称" in rejects[7]["reason"]
    assert "类型不符" in rejects[8]["reason"]
    assert "品类" in rejects[9]["reason"]
    assert "未声明字段" in rejects[10]["reason"]
    for r in rejects.values():
        assert r["raw_json"].strip().startswith("{")
        assert r["reason"]


def test_contract_edit_changes_what_is_rejected():
    fields = pipeline.get_contract(1)
    for f in fields:
        if f["field"] == "门店名称":
            f["required"] = False
    fields.append({"field": "备注", "required": False, "ftype": "文本"})
    pipeline.save_contract(1, fields)
    job = pipeline.run_load_paste(1)
    assert job["out_count"] == 8
    assert job["drop_count"] == 2
    reasons = [r["reason"] for r in pipeline.list_rejects(1)]
    assert not any("门店名称" in r for r in reasons)
    assert not any("备注" in r for r in reasons)


def test_save_contract_rejects_invalid_payload():
    with pytest.raises(ValueError, match="至少保留一个字段"):
        pipeline.save_contract(1, [])
    with pytest.raises(ValueError, match="类型无效"):
        pipeline.save_contract(1, [{"field": "金额", "required": True, "ftype": "字符串"}])
    with pytest.raises(ValueError, match="字段重复"):
        pipeline.save_contract(
            1,
            [
                {"field": "金额", "required": True, "ftype": "数值"},
                {"field": "金额", "required": False, "ftype": "数值"},
            ],
        )
    with pytest.raises(ValueError, match="数值列"):
        pipeline.save_contract(1, [{"field": "金额", "required": True, "ftype": "文本"}])
    with pytest.raises(ValueError, match="主题域不存在"):
        pipeline.save_contract(99, [{"field": "金额", "required": True, "ftype": "数值"}])


def test_validate_row_type_rules():
    contract = pipeline.DEFAULT_CONTRACT
    ok = {"业务日": "2026-11-10", "门店编码": "S01", "门店名称": "城东店",
          "品类": "饮料", "金额": 12.5, "件数": 3}
    assert pipeline.validate_row(ok, contract) == []
    assert pipeline.validate_row({**ok, "件数": 3.0}, contract) == []
    assert pipeline.validate_row({**ok, "件数": 3.5}, contract)
    assert pipeline.validate_row({**ok, "件数": True}, contract)
    assert pipeline.validate_row({**ok, "业务日": "2026-13-01"}, contract)
    assert pipeline.validate_row({**ok, "业务日": "20261110"}, contract)
    assert pipeline.validate_row({**ok, "金额": "12.5"}, contract)
