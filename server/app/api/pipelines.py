"""Pipeline CRUD and execution API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, ServiceAdminDep, ServiceMemberDep
from app.db.models import Pipeline, PipelineStatus, ServiceRole
from app.pipeline.executor import run_pipeline
from app.pipeline.preparation import check_readiness, prepare_pipeline
from app.pipeline.registry import get_node_schema
from app.pipeline.types import ExecutionContext
from app.pipeline.validation import validate_graph
from app.schemas.pipelines import (
    PipelineCreate,
    PipelineOut,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStatusUpdate,
    PipelineUpdate,
)

router = APIRouter(tags=["pipelines"])

_NODE_MODELS: dict[str, dict[str, list[str]]] = {
    "EmbedNode": {
        "ollama": [
            "nomic-embed-text",
            "mxbai-embed-large",
            "all-minilm",
            "bge-m3",
        ],
        "tei": [],
        "vllm": [
            "intfloat/e5-large-v2",
            "BAAI/bge-large-en-v1.5",
            "intfloat/multilingual-e5-large",
        ],
        "azure_openai": [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ],
    },
    "RerankNode": {
        "passthrough": [],
        "cross_encoder": [
            "BAAI/bge-reranker-base",
            "BAAI/bge-reranker-large",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "cross-encoder/ms-marco-MiniLM-L-12-v2",
        ],
        "cohere": [
            "rerank-v3.5",
            "rerank-multilingual-v3.0",
            "rerank-english-v3.0",
        ],
    },
}


@router.get("/pipeline-default")
def default_pipeline_graph(_user: CurrentUser) -> dict:
    """Return the system default pipeline graph derived from server config."""
    from app.core.config import get_settings
    settings = get_settings()
    emb = settings.embeddings
    emb_model_map: dict[str, str | None] = {
        "ollama": emb.ollama.model,
        "tei": None,
        "vllm": emb.vllm.model,
        "azure_openai": emb.azure_openai.deployment or None,
    }
    emb_model = emb_model_map.get(emb.provider)

    reranker = settings.search.reranker
    nodes: list[dict] = [
        {"id": "d-1", "type": "QueryInput",   "position": {"x": 80,   "y": 160}, "data": {"config": {}}},
        {"id": "d-2", "type": "EmbedNode",    "position": {"x": 280,  "y": 60},  "data": {"config": {"provider": emb.provider, "model": emb_model}}},
        {"id": "d-3", "type": "RetrieveNode", "position": {"x": 520,  "y": 120}, "data": {"config": {}}},
    ]
    edges: list[dict] = [
        {"id": "d-e1", "source": "d-1", "target": "d-2", "sourceHandle": "query",  "targetHandle": "query"},
        {"id": "d-e2", "source": "d-1", "target": "d-3", "sourceHandle": "query",  "targetHandle": "query"},
        {"id": "d-e3", "source": "d-2", "target": "d-3", "sourceHandle": "vector", "targetHandle": "vector"},
    ]

    if reranker is not None:
        nodes += [
            {"id": "d-4", "type": "RerankNode",  "position": {"x": 760,  "y": 60},  "data": {"config": {"provider": reranker.provider, "model": reranker.model}}},
            {"id": "d-5", "type": "EnrichNode",  "position": {"x": 1000, "y": 120}, "data": {"config": {}}},
            {"id": "d-6", "type": "OutputNode",  "position": {"x": 1200, "y": 200}, "data": {"config": {}}},
        ]
        edges += [
            {"id": "d-e4", "source": "d-3", "target": "d-4", "sourceHandle": "hits",    "targetHandle": "hits"},
            {"id": "d-e5", "source": "d-1", "target": "d-4", "sourceHandle": "query",   "targetHandle": "query"},
            {"id": "d-e6", "source": "d-4", "target": "d-5", "sourceHandle": "hits",    "targetHandle": "hits"},
            {"id": "d-e7", "source": "d-5", "target": "d-6", "sourceHandle": "results", "targetHandle": "results"},
        ]
    else:
        nodes += [
            {"id": "d-4", "type": "EnrichNode", "position": {"x": 760, "y": 120}, "data": {"config": {}}},
            {"id": "d-5", "type": "OutputNode", "position": {"x": 960, "y": 200}, "data": {"config": {}}},
        ]
        edges += [
            {"id": "d-e4", "source": "d-3", "target": "d-4", "sourceHandle": "hits",    "targetHandle": "hits"},
            {"id": "d-e5", "source": "d-4", "target": "d-5", "sourceHandle": "results", "targetHandle": "results"},
        ]

    return {"nodes": nodes, "edges": edges}


@router.get("/pipeline-schema")
def pipeline_schema(_user: CurrentUser) -> dict:
    import app.pipeline.nodes  # noqa: F401
    return get_node_schema()


@router.get("/pipeline-node-models")
def pipeline_node_models(_user: CurrentUser) -> dict:
    return _NODE_MODELS


@router.get("/services/{service_id}/pipelines", response_model=list[PipelineOut])
def list_pipelines(service_id: int, db: DbDep, membership: ServiceMemberDep) -> list[Pipeline]:
    stmt = select(Pipeline).where(Pipeline.service_id == service_id)
    if membership.role != ServiceRole.admin:
        stmt = stmt.where(Pipeline.status == PipelineStatus.active)
    return list(db.execute(stmt).scalars())


@router.post("/services/{service_id}/pipelines", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(service_id: int, payload: PipelineCreate, db: DbDep, _membership: ServiceAdminDep) -> Pipeline:
    errors = validate_graph(payload.graph_json)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
    pipeline = Pipeline(service_id=service_id, name=payload.name, graph_json=payload.graph_json)
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.get("/services/{service_id}/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(service_id: int, pipeline_id: int, db: DbDep, _membership: ServiceMemberDep) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    return pipeline


@router.put("/services/{service_id}/pipelines/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    service_id: int,
    pipeline_id: int,
    payload: PipelineUpdate,
    db: DbDep,
    _membership: ServiceAdminDep,
) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    if payload.graph_json is not None:
        errors = validate_graph(payload.graph_json)
        if errors:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
        pipeline.graph_json = payload.graph_json
    if payload.name is not None:
        pipeline.name = payload.name
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.delete("/services/{service_id}/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(service_id: int, pipeline_id: int, db: DbDep, _membership: ServiceAdminDep) -> None:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    db.delete(pipeline)
    db.commit()


@router.patch("/services/{service_id}/pipelines/{pipeline_id}/status", response_model=PipelineOut)
def update_pipeline_status(
    service_id: int,
    pipeline_id: int,
    payload: PipelineStatusUpdate,
    db: DbDep,
    _membership: ServiceAdminDep,
) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    if payload.status == PipelineStatus.archived and pipeline.status == PipelineStatus.archived:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pipeline is already archived")
    if payload.status == PipelineStatus.active:
        errors = validate_graph(pipeline.graph_json)
        if errors:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
    pipeline.status = payload.status
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.get("/services/{service_id}/pipelines/{pipeline_id}/readiness")
def pipeline_readiness(service_id: int, pipeline_id: int, db: DbDep, _membership: ServiceMemberDep) -> dict:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    return check_readiness(pipeline.graph_json)


@router.post("/services/{service_id}/pipelines/{pipeline_id}/prepare")
def prepare_pipeline_endpoint(service_id: int, pipeline_id: int, db: DbDep, _membership: ServiceMemberDep) -> dict:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
    try:
        prepare_pipeline(pipeline.graph_json)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return {"ready": True}


@router.post("/services/{service_id}/pipelines/{pipeline_id}/run", response_model=PipelineRunResponse)
def run_pipeline_endpoint(
    service_id: int,
    pipeline_id: int,
    payload: PipelineRunRequest,
    db: DbDep,
    _membership: ServiceMemberDep,
) -> PipelineRunResponse:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline or pipeline.service_id != service_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")

    errors = validate_graph(pipeline.graph_json)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    ctx = ExecutionContext(
        db=db,
        service_id=service_id,
        run_inputs={"query": payload.query, "top_k": payload.top_k},
    )
    try:
        results, node_timings = run_pipeline(pipeline.graph_json, ctx)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    serialized = [
        {
            "document_id": r.document_id,
            "document_title": r.document_title,
            "ordinal": r.ordinal,
            "score": r.score,
            "text": r.text,
            "metadata": r.metadata,
        }
        for r in results
    ]
    return PipelineRunResponse(
        pipeline_id=pipeline_id,
        query=payload.query,
        results=serialized,
        node_timings=node_timings,
    )
