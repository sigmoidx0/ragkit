"""Demo MCP server: a factory maintenance desk with mock data.

Equipment with live-looking sensor readings and alarms, technicians, and work
orders. Lookups are marked read-only, so ragkit runs them straight away; creating,
assigning and closing work orders change state, so an agent needs the user's
approval first. The board at http://localhost:8765/ shows the work orders as
they change, which makes the approval flow visible during a demo.

State lives in memory and resets on restart.

    cd server
    MCP_TOKEN_MAINTENANCE=demo-token uv run python -m demo.maintenance_mcp

Register it in ragkit as http://localhost:8765/mcp with the token variable
MCP_TOKEN_MAINTENANCE (set to the same value in ragkit's environment).
"""

from __future__ import annotations

import itertools
import os
from datetime import date, datetime, timedelta
from typing import Literal

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

TOKEN_ENV = "MCP_TOKEN_MAINTENANCE"
PORT = int(os.getenv("MAINTENANCE_MCP_PORT", "8765"))

mcp = FastMCP(
    "maintenance-desk",
    instructions="Factory maintenance desk: equipment status, alarms, technicians and work orders.",
    stateless_http=True,
    json_response=True,
)

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
CLOSE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)

Priority = Literal["low", "medium", "high", "urgent"]

# ── Mock data ────────────────────────────────────────────────────────────────

_today = date.today()
EQUIPMENT = {
    "PR-101": {"name": "프레스 1호기", "line": "프레스 1라인", "status": "running",
               "temperature_c": 61.2, "vibration_mm_s": 2.1, "last_maintenance": str(_today - timedelta(days=21)),
               "alarms": []},
    "PR-102": {"name": "프레스 2호기", "line": "프레스 1라인", "status": "warning",
               "temperature_c": 78.5, "vibration_mm_s": 7.9, "last_maintenance": str(_today - timedelta(days=96)),
               "alarms": ["진동 경고: 7.9 mm/s (기준 7.1 초과)", "유압 압력 변동 ±8%"]},
    "IM-201": {"name": "사출성형기 A", "line": "사출 2라인", "status": "running",
               "temperature_c": 212.0, "vibration_mm_s": 1.4, "last_maintenance": str(_today - timedelta(days=12)),
               "alarms": []},
    "IM-202": {"name": "사출성형기 B", "line": "사출 2라인", "status": "stopped",
               "temperature_c": 25.3, "vibration_mm_s": 0.0, "last_maintenance": str(_today - timedelta(days=140)),
               "alarms": ["히터 밴드 3구역 단선 의심", "비상정지 작동 (오늘 06:42)"]},
    "CN-301": {"name": "CNC 머시닝센터", "line": "가공 3라인", "status": "running",
               "temperature_c": 44.8, "vibration_mm_s": 3.3, "last_maintenance": str(_today - timedelta(days=33)),
               "alarms": ["스핀들 부하 85% 지속 (30분)"]},
    "RB-401": {"name": "용접 로봇 1호", "line": "용접 4라인", "status": "running",
               "temperature_c": 39.1, "vibration_mm_s": 1.0, "last_maintenance": str(_today - timedelta(days=8)),
               "alarms": []},
}
TECHNICIANS = {
    "T-01": {"name": "김정비", "skills": ["유압", "프레스"], "on_shift": True},
    "T-02": {"name": "이전기", "skills": ["전기", "히터", "사출"], "on_shift": True},
    "T-03": {"name": "박가공", "skills": ["CNC", "스핀들"], "on_shift": False},
    "T-04": {"name": "최로봇", "skills": ["로봇", "용접"], "on_shift": True},
}
_ids = itertools.count(1001)
WORK_ORDERS: dict[str, dict] = {}


def _seed() -> None:
    wo_id = f"WO-{next(_ids)}"
    WORK_ORDERS[wo_id] = {
        "id": wo_id, "equipment_id": "CN-301", "title": "스핀들 베어링 정기 점검",
        "description": "분기 정기 점검", "priority": "medium", "status": "in_progress",
        "assignee": "T-03", "due_date": str(_today + timedelta(days=2)),
        "created_at": (datetime.now() - timedelta(hours=5)).isoformat(timespec="minutes"),
        "resolution": None,
    }


_seed()


def _equipment(equipment_id: str) -> dict:
    eq = EQUIPMENT.get(equipment_id.strip().upper())
    if eq is None:
        raise ValueError(f"unknown equipment '{equipment_id}'. Known: {', '.join(EQUIPMENT)}")
    return eq


def _work_order(work_order_id: str) -> dict:
    wo = WORK_ORDERS.get(work_order_id.strip().upper())
    if wo is None:
        raise ValueError(f"unknown work order '{work_order_id}'")
    return wo


def _summary(eq_id: str, eq: dict) -> dict:
    return {"id": eq_id, **{k: v for k, v in eq.items()}}


# ── Read-only tools ──────────────────────────────────────────────────────────

@mcp.tool(title="설비 목록 조회", annotations=READ)
def list_equipment(line: str | None = None) -> list[dict]:
    """List factory equipment with status (running/warning/stopped), temperature,
    vibration, last maintenance date and active alarms. Optionally filter by line
    name (e.g. '프레스 1라인')."""
    return [_summary(i, e) for i, e in EQUIPMENT.items() if not line or line in e["line"]]


@mcp.tool(title="설비 상세 조회", annotations=READ)
def get_equipment(equipment_id: str) -> dict:
    """Details of one piece of equipment (e.g. 'PR-102'), including alarms and its open work orders."""
    eq = _equipment(equipment_id)
    eq_id = equipment_id.strip().upper()
    open_orders = [w for w in WORK_ORDERS.values() if w["equipment_id"] == eq_id and w["status"] != "done"]
    return {**_summary(eq_id, eq), "open_work_orders": open_orders}


@mcp.tool(title="작업지시 목록 조회", annotations=READ)
def list_work_orders(status: Literal["open", "in_progress", "done", "all"] = "all") -> list[dict]:
    """List maintenance work orders, newest first. Filter by status if given."""
    orders = sorted(WORK_ORDERS.values(), key=lambda w: w["created_at"], reverse=True)
    return [w for w in orders if status == "all" or w["status"] == status]


@mcp.tool(title="정비 기사 조회", annotations=READ)
def list_technicians() -> list[dict]:
    """Maintenance technicians with their skills and whether they are on shift."""
    return [{"id": i, **t} for i, t in TECHNICIANS.items()]


# ── Tools that change state ──────────────────────────────────────────────────

@mcp.tool(title="작업지시 생성", annotations=WRITE)
def create_work_order(
    equipment_id: str,
    title: str,
    priority: Priority = "medium",
    description: str = "",
    due_date: str | None = None,
) -> dict:
    """Create a maintenance work order for a piece of equipment.

    equipment_id is the equipment's ID, not its name: PR-101 프레스 1호기,
    PR-102 프레스 2호기, IM-201 사출성형기 A, IM-202 사출성형기 B,
    CN-301 CNC 머시닝센터, RB-401 용접 로봇 1호 (list_equipment has them all).
    due_date is YYYY-MM-DD; leave it out for the default (urgent → today,
    high → tomorrow, otherwise in 3 days)."""
    _equipment(equipment_id)
    days = {"urgent": 0, "high": 1}.get(priority, 3)
    wo_id = f"WO-{next(_ids)}"
    WORK_ORDERS[wo_id] = {
        "id": wo_id, "equipment_id": equipment_id.strip().upper(), "title": title.strip(),
        "description": description.strip(), "priority": priority, "status": "open", "assignee": None,
        "due_date": due_date or str(date.today() + timedelta(days=days)),
        "created_at": datetime.now().isoformat(timespec="minutes"), "resolution": None,
    }
    return WORK_ORDERS[wo_id]


@mcp.tool(title="정비 기사 배정", annotations=WRITE)
def assign_technician(work_order_id: str, technician_id: str) -> dict:
    """Assign a technician to a work order; it moves to in_progress.

    technician_id is the ID, not the name: T-01 김정비 (유압·프레스), T-02 이전기
    (전기·히터·사출), T-03 박가공 (CNC), T-04 최로봇 (로봇·용접). Work order IDs look
    like WO-1002 — find them with list_work_orders."""
    wo = _work_order(work_order_id)
    tech_id = technician_id.strip().upper()
    if tech_id not in TECHNICIANS:
        raise ValueError(f"unknown technician '{technician_id}'. Known: {', '.join(TECHNICIANS)}")
    if wo["status"] == "done":
        raise ValueError(f"{wo['id']} is already closed")
    wo.update(assignee=tech_id, status="in_progress")
    return wo


@mcp.tool(title="작업지시 완료 처리", annotations=CLOSE)
def close_work_order(work_order_id: str, resolution: str) -> dict:
    """Close a work order (ID like WO-1002) with a short description of what was done."""
    wo = _work_order(work_order_id)
    wo.update(status="done", resolution=resolution.strip())
    return wo


# ── Board page (for watching the demo) ───────────────────────────────────────

@mcp.custom_route("/api/board", methods=["GET"])
async def board_data(_: Request) -> Response:
    return JSONResponse({
        "equipment": [_summary(i, e) for i, e in EQUIPMENT.items()],
        "technicians": TECHNICIANS,
        "work_orders": sorted(WORK_ORDERS.values(), key=lambda w: w["created_at"], reverse=True),
    })


@mcp.custom_route("/", methods=["GET"])
async def board(_: Request) -> Response:
    return HTMLResponse(BOARD_HTML)


BOARD_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>정비 보드 · Maintenance desk</title>
<style>
:root{--bg:#0f1720;--card:#16212d;--line:#243344;--ink:#e6edf3;--mute:#8aa0b3;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--acc:#38bdf8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,"Apple SD Gothic Neo",sans-serif;padding:24px}
h1{font-size:20px;margin:0 0 4px}p.sub{color:var(--mute);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin-bottom:24px}
.eq{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.eq b{display:block}.eq small{color:var(--mute)}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.running{background:var(--ok)}.warning{background:var(--warn)}.stopped{background:var(--bad)}
.al{color:var(--warn);font-size:12px;margin-top:6px}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--mute);font-weight:600;font-size:12px}
.pill{font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line)}
.open{color:var(--acc);border-color:var(--acc)}.in_progress{color:var(--warn);border-color:var(--warn)}.done{color:var(--ok);border-color:var(--ok)}
.urgent{color:var(--bad)}.high{color:var(--warn)}tr.new{animation:flash 2s}
@keyframes flash{from{background:#1e3a5f}to{background:transparent}}
</style></head><body>
<h1>정비 보드</h1><p class="sub">Maintenance desk MCP · 2초마다 갱신 · 상태는 서버 메모리에만 있습니다</p>
<div class="grid" id="eq"></div><h1 style="font-size:16px;margin-bottom:8px">작업지시</h1>
<table><thead><tr><th>ID</th><th>설비</th><th>제목</th><th>우선순위</th><th>상태</th><th>담당</th><th>기한</th><th>처리 내용</th></tr></thead><tbody id="wo"></tbody></table>
<script>
let seen=new Set();const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function load(){const d=await (await fetch('/api/board')).json();
document.getElementById('eq').innerHTML=d.equipment.map(e=>`<div class="eq"><b><span class="dot ${e.status}"></span>${esc(e.name)} <small>${e.id}</small></b><small>${esc(e.line)} · ${e.temperature_c}°C · 진동 ${e.vibration_mm_s} mm/s</small>${e.alarms.map(a=>`<div class="al">⚠ ${esc(a)}</div>`).join('')}</div>`).join('');
document.getElementById('wo').innerHTML=d.work_orders.map(w=>{const isNew=seen.size&&!seen.has(w.id+w.status);return `<tr class="${isNew?'new':''}"><td>${w.id}</td><td>${w.equipment_id}</td><td>${esc(w.title)}</td><td class="${w.priority}">${w.priority}</td><td><span class="pill ${w.status}">${w.status}</span></td><td>${w.assignee?esc(d.technicians[w.assignee]?.name||w.assignee):'—'}</td><td>${w.due_date}</td><td>${esc(w.resolution||'')}</td></tr>`}).join('');
seen=new Set(d.work_orders.map(w=>w.id+w.status));}
load();setInterval(load,2000);
</script></body></html>"""


# ── Auth + entry point ───────────────────────────────────────────────────────

def build_app():
    app = mcp.streamable_http_app()
    token = os.getenv(TOKEN_ENV)

    async def require_token(scope, receive, send):
        # The board is public; the MCP endpoint needs the bearer token when one is set.
        if token and scope["type"] == "http" and scope["path"].startswith("/mcp"):
            headers = dict(scope.get("headers") or [])
            if headers.get(b"authorization", b"").decode() != f"Bearer {token}":
                response = JSONResponse({"error": "missing or invalid bearer token"}, status_code=401)
                return await response(scope, receive, send)
        return await app(scope, receive, send)

    return require_token


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=PORT, log_level="info")
