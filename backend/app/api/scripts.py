"""Script management API — CRUD + test execution."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.script import Script
from app.models.device import DeviceTag
from app.schemas.common import PageResponse
from app.engine.script_engine import script_engine

router = APIRouter(prefix="/scripts", tags=["脚本算法"])


class ScriptCreate(BaseModel):
    name: str
    description: str = ""
    language: str = "python"
    code: str
    default_params: str = "{}"
    timeout_ms: int = 1000
    max_history: int = 100
    enabled: bool = True

class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    default_params: Optional[str] = None
    timeout_ms: Optional[int] = None
    max_history: Optional[int] = None
    enabled: Optional[bool] = None

class ScriptOut(BaseModel):
    id: int
    name: str
    description: str
    language: str
    code: str
    default_params: str
    timeout_ms: int
    max_history: int
    is_template: bool
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class TestRequest(BaseModel):
    code: str
    raw_value: float = 100.0
    history: List[float] = []
    tag_config: dict = {}

class AssignRequest(BaseModel):
    tag_id: int
    script_id: Optional[int] = None  # None to unassign


@router.get("")
def list_scripts(
    enabled_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("script.read")),
):
    q = db.query(Script)
    if enabled_only:
        q = q.filter(Script.enabled == True)
    return q.order_by(Script.is_template.desc(), Script.name).all()


@router.get("/{script_id}", response_model=ScriptOut)
def get_script(script_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("script.read"))):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return script


@router.post("", response_model=ScriptOut)
def create_script(req: ScriptCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("script.write"))):
    script = Script(**req.model_dump())
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


@router.put("/{script_id}", response_model=ScriptOut)
def update_script(script_id: int, req: ScriptUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("script.write"))):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(script, k, v)
    db.commit()
    db.refresh(script)
    # Invalidate cache
    script_engine.invalidate_cache(script_id)
    return script


@router.delete("/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("script.write"))):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")
    if script.is_template:
        raise HTTPException(status_code=400, detail="系统模板不可删除")
    # Check if any tag uses this script
    tag_count = db.query(DeviceTag).filter(DeviceTag.script_id == script_id).count()
    if tag_count > 0:
        raise HTTPException(status_code=400, detail=f"该脚本被 {tag_count} 个点位使用，请先解除绑定")
    db.delete(script)
    db.commit()
    return {"message": "删除成功"}


@router.post("/test")
def test_script(req: TestRequest, _: User = Depends(require_permission("script.write"))):
    """Test execute a script with sample data."""
    result = script_engine.test_execute(
        code=req.code,
        raw_value=req.raw_value,
        history=req.history,
        tag_config=req.tag_config,
    )
    return result


@router.post("/assign")
def assign_script(req: AssignRequest, db: Session = Depends(get_db), _: User = Depends(require_permission("script.write"))):
    """Assign or unassign a script to/from a tag."""
    tag = db.query(DeviceTag).filter(DeviceTag.id == req.tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="点位不存在")
    tag.script_id = req.script_id
    db.commit()
    action = f"绑定脚本#{req.script_id}" if req.script_id else "解除脚本绑定"
    return {"message": f"点位 {tag.name} {action}成功"}


# ── Script templates (pre-defined) ──

SCRIPT_TEMPLATES = [
    {
        "id": "linear_calibration",
        "name": "线性标定",
        "description": "y = raw * a + b，用于传感器标定",
        "code": "def process(raw_value, history, tag, context):\n    a = tag.get('params', {}).get('a', 1.0)\n    b = tag.get('params', {}).get('b', 0.0)\n    return raw_value * a + b",
        "default_params": '{"a": 1.0, "b": 0.0}',
    },
    {
        "id": "moving_average",
        "name": "滑动平均滤波",
        "description": "对最近N个值取平均，消除波动",
        "code": "def process(raw_value, history, tag, context):\n    window = tag.get('params', {}).get('window', 10)\n    values = history[-(window-1):] + [raw_value]\n    return sum(values) / len(values)",
        "default_params": '{"window": 10}',
    },
    {
        "id": "moving_median",
        "name": "滑动中值滤波",
        "description": "对最近N个值取中值，消除尖峰干扰",
        "code": "def process(raw_value, history, tag, context):\n    window = tag.get('params', {}).get('window', 5)\n    values = sorted(history[-(window-1):] + [raw_value])\n    n = len(values)\n    if n % 2 == 0:\n        return (values[n//2 - 1] + values[n//2]) / 2\n    return values[n//2]",
        "default_params": '{"window": 5}',
    },
    {
        "id": "rate_of_change",
        "name": "变化率计算",
        "description": "计算每秒变化量",
        "code": "def process(raw_value, history, tag, context):\n    if not history:\n        return 0.0\n    prev = history[-1]\n    delta = raw_value - prev\n    return delta  # per-poll change rate",
        "default_params": '{}',
    },
    {
        "id": "accumulator",
        "name": "累计器",
        "description": "对值进行累加（如流量累计）",
        "code": "def process(raw_value, history, tag, context):\n    if not history:\n        return raw_value\n    return history[-1] + raw_value",
        "default_params": '{}',
    },
    {
        "id": "dead_band",
        "name": "死区滤波",
        "description": "变化小于死区范围时保持上次值",
        "code": "def process(raw_value, history, tag, context):\n    deadband = tag.get('params', {}).get('deadband', 1.0)\n    if history and abs(raw_value - history[-1]) < deadband:\n        return history[-1]\n    return raw_value",
        "default_params": '{"deadband": 1.0}',
    },
    {
        "id": "range_mapper",
        "name": "量程映射",
        "description": "将原始范围映射到目标范围（如 4-20mA → 0-100%）",
        "code": "def process(raw_value, history, tag, context):\n    p = tag.get('params', {})\n    in_min = p.get('in_min', 4)\n    in_max = p.get('in_max', 20)\n    out_min = p.get('out_min', 0)\n    out_max = p.get('out_max', 100)\n    if in_max == in_min:\n        return out_min\n    return (raw_value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min",
        "default_params": '{"in_min": 4, "in_max": 20, "out_min": 0, "out_max": 100}',
    },
    {
        "id": "alarm_threshold",
        "name": "阈值报警脚本",
        "description": "超过阈值时返回报警信息",
        "code": "def process(raw_value, history, tag, context):\n    p = tag.get('params', {})\n    high = p.get('high_limit', 100)\n    low = p.get('low_limit', 0)\n    if raw_value > high:\n        return {'value': raw_value, 'quality': 'bad', 'alarm': f'值 {raw_value:.1f} 超过上限 {high}'}\n    if raw_value < low:\n        return {'value': raw_value, 'quality': 'bad', 'alarm': f'值 {raw_value:.1f} 低于下限 {low}'}\n    return raw_value",
        "default_params": '{"high_limit": 100, "low_limit": 0}',
    },
]


@router.get("/templates/all")
def get_script_templates(_: User = Depends(require_permission("script.read"))):
    return SCRIPT_TEMPLATES
