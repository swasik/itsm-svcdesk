# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.6 and 1.7; the lecturer ran the tests
"""The HTTP layer: FastAPI routes, JSON error bodies and the per-request clock."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .clock import parse_instant, real_now
from .config import Settings
from .db import Database
from .dora import DoraError, compute, parse_instant as parse_dora_instant
from .kb import KbClient
from .metrics import MetricsMiddleware, exposition
from .models import TicketCreate
from .service import ACTIONS, ApiError, TicketService
from .ticketevents import ticket_events

CLOCK_HEADER = "x-test-clock"


def bind_clock(request: Request) -> None:
    """App-wide dependency: decide `now` for this request and keep it on `request.state`.

    With the test clock enabled and the header present, `now` is the header's instant; a header that does
    not parse (or has no offset) is a 400. With the test clock disabled the header is ignored.
    """
    settings: Settings = request.app.state.settings
    header = request.headers.get(CLOCK_HEADER)
    if settings.test_clock and header is not None:
        try:
            request.state.now = parse_instant(header)
        except ValueError as exc:
            raise ApiError(400, "invalid_test_clock", str(exc)) from exc
    else:
        request.state.now = real_now()


def request_now(request: Request) -> datetime:
    return request.state.now


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = Settings.from_env() if settings is None else settings
    db = Database(settings.db_path)
    service = TicketService(settings, db)
    kb = KbClient(settings.kb_index_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await kb.close()
        db.close()

    app = FastAPI(
        title="svcdesk",
        version=__version__,
        dependencies=[Depends(bind_clock)],
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.service = service
    app.state.kb = kb
    app.add_middleware(MetricsMiddleware)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": [str(part) for part in error.get("loc", ())], "msg": error.get("msg"), "type": error.get("type")}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "request body is invalid", "details": details}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        code = codes.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        if exc.status_code == 404:
            message = f"no route for {request.method} {request.url.path}"
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": message}},
                            headers=getattr(exc, "headers", None))

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "svcdesk",
            "version": __version__,
            "resolutions": settings.resolutions,
            "test_clock": settings.test_clock,
        }

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        body, content_type = exposition()
        return Response(content=body, media_type=content_type)

    @app.get("/kb/search")
    async def kb_search(q: str | None = None) -> dict:
        """Knowledge-base search through the kb-index dependency (design/LAB3.md M-02)."""
        return await kb.search(q)

    @app.post("/tickets", status_code=201)
    def create_ticket(body: TicketCreate, now: datetime = Depends(request_now)) -> dict:
        return service.create(body, now).to_json()

    @app.get("/tickets")
    def list_tickets(state: str | None = None, priority: str | None = None) -> list[dict]:
        return [ticket.to_json() for ticket in service.list(state, priority)]

    @app.get("/tickets/{ticket_id}")
    def get_ticket(ticket_id: str) -> dict:
        return service.get(ticket_id).to_json()

    @app.get("/tickets/{ticket_id}/sla")
    def get_sla(ticket_id: str, now: datetime = Depends(request_now)) -> dict:
        return service.sla_view(ticket_id, now)

    @app.post("/dora/metrics")
    async def dora_metrics(request: Request) -> dict:
        """The five delivery metrics of a supplied event log (design/LAB2.md 4.1).

        Stateless: a pure function of the request body, so two identical requests answer identically and
        no ordering between requests exists. Every malformed input is a 400 with a top-level `error`.
        """
        try:
            body = await request.json()
        except ValueError as exc:
            raise ApiError(400, "invalid_json", f"request body is not JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise ApiError(400, "invalid_request", "request body must be a JSON object")
        window = body.get("window")
        if not isinstance(window, dict):
            raise ApiError(400, "invalid_window", "window: expected an object with `from` and `to`")
        try:
            window_from = parse_dora_instant(window.get("from"), "window.from")
            window_to = parse_dora_instant(window.get("to"), "window.to")
            return compute(body.get("events"), window_from, window_to)
        except DoraError as exc:
            raise ApiError(400, "invalid_event_log", str(exc)) from exc

    @app.get("/dora/ticket-events")
    def dora_ticket_events() -> list[dict]:
        return ticket_events(service.list(None, None))

    def _register_action(action: str) -> None:
        @app.post(f"/tickets/{{ticket_id}}/{action}", name=action)
        def _action(ticket_id: str, now: datetime = Depends(request_now)) -> dict:
            return service.act(ticket_id, action, now).to_json()

    for action in ACTIONS:
        _register_action(action)

    return app
