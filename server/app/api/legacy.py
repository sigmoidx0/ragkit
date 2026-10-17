"""Pre-rename routes, kept for the external ragkit-mcp adapter.

Workspaces were called services until revision 0014, and the MCP adapter (a
separate repository) still calls these paths. They run the same handlers as
their /workspaces counterparts; drop them once the adapter is updated.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import documents, search
from app.schemas.documents import DocumentListResponse, DocumentOut
from app.schemas.search import SearchResponse

router = APIRouter(tags=["legacy"], include_in_schema=False)

router.add_api_route(
    "/services/{workspace_id}/search", search.search, methods=["POST"], response_model=SearchResponse
)
router.add_api_route(
    "/services/{workspace_id}/documents",
    documents.list_documents,
    methods=["GET"],
    response_model=DocumentListResponse,
)
router.add_api_route(
    "/services/{workspace_id}/documents/{document_id}",
    documents.get_document,
    methods=["GET"],
    response_model=DocumentOut,
)
