"""Local-only HTTP API for approved production search jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import ipaddress
import re
import secrets
import threading
from typing import Annotated
from typing import Literal
from typing import Protocol

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response
from starlette.routing import Route

from src.search_v2.production_search import ProductionSearchCommand
from src.search_v2.production_search import ProductionSearchError
from src.search_v2.provisional_history_repository import ProvisionalHistoryDetail
from src.search_v2.provisional_history_repository import ProvisionalHistoryInputError
from src.search_v2.provisional_history_repository import ProvisionalHistoryNotFoundError
from src.search_v2.provisional_history_repository import ProvisionalHistoryStorageError
from src.search_v2.search_job import LOCAL_SEARCH_OWNER_ID
from src.search_v2.search_job import SearchJobInputError
from src.search_v2.search_job import SearchJobNotFoundError
from src.search_v2.search_job import SearchJobSnapshot
from src.search_v2.search_job import SearchJobStateError
from src.search_v2.search_job import SearchJobStorageError


SEARCH_SUBMISSION_HEADER = "x-amazon-explorer-submission"
_CAPABILITY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
_CANCELLABLE_STATUSES = {"queued", "running"}
_MAX_SUBMISSION_LIFETIME = timedelta(minutes=15)
_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}

SubmissionCapability = Annotated[
    str,
    StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


class _StrictFrozenContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class ProductionSubmission(_StrictFrozenContract):
    capability: SubmissionCapability = Field(repr=False)
    expires_at: datetime


class SearchJobApiView(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    locator: str
    status: Literal[
        "queued",
        "running",
        "cancel_requested",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
    ]
    can_cancel: bool
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    result_locator: str | None


class HistoryReferenceApiView(_StrictFrozenContract):
    locator: str
    target: Literal["desired", "counterfactual"]
    condition_id: str | None
    content_type: Literal["image/png"]
    width: int
    height: int


class HistoryProductApiView(_StrictFrozenContract):
    rank: int
    title: str
    price_jpy: int | None
    product_url: str | None
    required_status: Literal["confirmed", "uncertain", "contradicted"]
    image_component_status: Literal["available", "missing", "unknown"]


class SearchHistoryApiView(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    locator: str
    completed_at: datetime
    expires_at: datetime
    summary: str
    reference_images: tuple[HistoryReferenceApiView, ...]
    products: tuple[HistoryProductApiView, ...]


class ErrorApiView(_StrictFrozenContract):
    schema_version: Literal["1.0"]
    error: Literal[
        "internal_error",
        "local_only",
        "method_not_allowed",
        "not_found",
        "search_not_available",
        "state_conflict",
        "temporarily_unavailable",
    ]


class _ProductionService(Protocol):
    def submit(self, command: ProductionSearchCommand) -> SearchJobSnapshot: ...

    def get(self, locator: str) -> SearchJobSnapshot: ...

    def cancel(self, locator: str) -> SearchJobSnapshot: ...


class _HistoryRepository(Protocol):
    def get(
        self,
        *,
        owner_id: str,
        locator: str,
        now: datetime,
    ) -> ProvisionalHistoryDetail: ...


class _SubmissionNotFoundError(RuntimeError):
    pass


@dataclass(slots=True, repr=False)
class _SubmissionEntry:
    expires_at: datetime
    command: ProductionSearchCommand | None
    job_locator: str | None = None


def _utc_datetime(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError("UTC datetime is required")
    if value.utcoffset() != timedelta(0):
        raise ValueError("UTC datetime is required")
    return value.astimezone(timezone.utc)


class InMemoryProductionSubmissionStore:
    """Keep approved commands process-local and expose only opaque capabilities."""

    def __init__(self) -> None:
        self._entries: dict[str, _SubmissionEntry] = {}
        self._lock = threading.Lock()

    def register(
        self,
        command: ProductionSearchCommand,
        *,
        now: datetime,
        expires_at: datetime,
    ) -> ProductionSubmission:
        if type(command) is not ProductionSearchCommand:
            raise ValueError("Production submission is invalid") from None
        current = _utc_datetime(now)
        expiry = _utc_datetime(expires_at)
        if expiry <= current or expiry > current + _MAX_SUBMISSION_LIFETIME:
            raise ValueError("Production submission is invalid") from None
        capability = secrets.token_urlsafe(32)
        with self._lock:
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= current]
            for key in expired:
                del self._entries[key]
            while capability in self._entries:
                capability = secrets.token_urlsafe(32)
            self._entries[capability] = _SubmissionEntry(
                expires_at=expiry,
                command=command,
            )
        return ProductionSubmission(capability=capability, expires_at=expiry)

    def submit(
        self,
        capability: object,
        *,
        service: _ProductionService,
        now: datetime,
    ) -> SearchJobSnapshot:
        current = _utc_datetime(now)
        if type(capability) is not str or _CAPABILITY_PATTERN.fullmatch(capability) is None:
            raise _SubmissionNotFoundError from None
        with self._lock:
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= current]
            for key in expired:
                del self._entries[key]
            entry = self._entries.get(capability)
            if entry is None:
                raise _SubmissionNotFoundError from None
            if entry.job_locator is not None:
                return service.get(entry.job_locator)
            if entry.command is None:
                raise _SubmissionNotFoundError from None
            snapshot = SearchJobSnapshot.model_validate(service.submit(entry.command))
            entry.command = None
            entry.job_locator = snapshot.locator
            return snapshot


def _job_view(snapshot: object) -> SearchJobApiView:
    job = SearchJobSnapshot.model_validate(snapshot)
    return SearchJobApiView(
        schema_version="1.0",
        locator=job.locator,
        status=job.status,
        can_cancel=job.status in _CANCELLABLE_STATUSES,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        result_locator=job.result_locator,
    )


def _history_view(detail: object) -> SearchHistoryApiView:
    history = ProvisionalHistoryDetail.model_validate(detail)
    references = tuple(
        HistoryReferenceApiView(
            locator=image.locator,
            target=image.target,
            condition_id=image.condition_id,
            content_type=image.content_type,
            width=image.width,
            height=image.height,
        )
        for image in history.reference_images
    )
    products = tuple(
        HistoryProductApiView(
            rank=product.rank,
            title=product.title,
            price_jpy=product.price_jpy,
            product_url=product.product_url,
            required_status=product.required_status,
            image_component_status=product.image_component_status,
        )
        for product in history.products
    )
    return SearchHistoryApiView(
        schema_version="1.0",
        locator=history.locator,
        completed_at=history.completed_at,
        expires_at=history.expires_at,
        summary=history.summary,
        reference_images=references,
        products=products,
    )


def _json(model: BaseModel, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        model.model_dump(mode="json"),
        status_code=status_code,
        headers=_RESPONSE_HEADERS,
    )


def _error(
    code: Literal[
        "internal_error",
        "local_only",
        "method_not_allowed",
        "not_found",
        "search_not_available",
        "state_conflict",
        "temporarily_unavailable",
    ],
    *,
    status_code: int,
) -> JSONResponse:
    return _json(
        ErrorApiView(schema_version="1.0", error=code),
        status_code=status_code,
    )


def _is_loopback(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def create_local_production_api(
    *,
    service: _ProductionService,
    history_repository: _HistoryRepository,
    submission_store: InMemoryProductionSubmissionStore,
    now: Callable[[], datetime],
) -> Starlette:
    """Create the loopback-only ASGI API without starting a server."""
    if (
        not callable(getattr(service, "submit", None))
        or not callable(getattr(service, "get", None))
        or not callable(getattr(service, "cancel", None))
        or not callable(getattr(history_repository, "get", None))
        or type(submission_store) is not InMemoryProductionSubmissionStore
        or not callable(now)
    ):
        raise ValueError("Production API dependencies are invalid") from None

    def current_time() -> datetime:
        return _utc_datetime(now())

    def local_guard(request: Request) -> Response | None:
        if _is_loopback(request):
            return None
        return _error("local_only", status_code=403)

    def submit_job(request: Request) -> Response:
        rejected = local_guard(request)
        if rejected is not None:
            return rejected
        try:
            snapshot = submission_store.submit(
                request.headers.get(SEARCH_SUBMISSION_HEADER),
                service=service,
                now=current_time(),
            )
            return _json(_job_view(snapshot), status_code=202)
        except _SubmissionNotFoundError:
            return _error("not_found", status_code=404)
        except ProductionSearchError:
            return _error("search_not_available", status_code=409)
        except (SearchJobInputError, SearchJobNotFoundError):
            return _error("not_found", status_code=404)
        except SearchJobStateError:
            return _error("state_conflict", status_code=409)
        except SearchJobStorageError:
            return _error("temporarily_unavailable", status_code=503)
        except (TypeError, ValidationError, ValueError):
            return _error("internal_error", status_code=500)
        except Exception:
            return _error("internal_error", status_code=500)

    def get_job(request: Request) -> Response:
        rejected = local_guard(request)
        if rejected is not None:
            return rejected
        try:
            return _json(_job_view(service.get(request.path_params["locator"])))
        except (SearchJobInputError, SearchJobNotFoundError):
            return _error("not_found", status_code=404)
        except SearchJobStorageError:
            return _error("temporarily_unavailable", status_code=503)
        except (TypeError, ValidationError, ValueError):
            return _error("internal_error", status_code=500)
        except Exception:
            return _error("internal_error", status_code=500)

    def cancel_job(request: Request) -> Response:
        rejected = local_guard(request)
        if rejected is not None:
            return rejected
        locator = request.path_params["locator"]
        try:
            current = SearchJobSnapshot.model_validate(service.get(locator))
            if current.status not in _CANCELLABLE_STATUSES:
                return _error("state_conflict", status_code=409)
            cancelled = SearchJobSnapshot.model_validate(service.cancel(locator))
            if cancelled.status not in {"cancel_requested", "cancelled"}:
                return _error("state_conflict", status_code=409)
            return _json(_job_view(cancelled))
        except (SearchJobInputError, SearchJobNotFoundError):
            return _error("not_found", status_code=404)
        except SearchJobStateError:
            return _error("state_conflict", status_code=409)
        except SearchJobStorageError:
            return _error("temporarily_unavailable", status_code=503)
        except (TypeError, ValidationError, ValueError):
            return _error("internal_error", status_code=500)
        except Exception:
            return _error("internal_error", status_code=500)

    def get_history(request: Request) -> Response:
        rejected = local_guard(request)
        if rejected is not None:
            return rejected
        try:
            detail = history_repository.get(
                owner_id=LOCAL_SEARCH_OWNER_ID,
                locator=request.path_params["locator"],
                now=current_time(),
            )
            return _json(_history_view(detail))
        except (ProvisionalHistoryInputError, ProvisionalHistoryNotFoundError):
            return _error("not_found", status_code=404)
        except ProvisionalHistoryStorageError:
            return _error("temporarily_unavailable", status_code=503)
        except (TypeError, ValidationError, ValueError):
            return _error("internal_error", status_code=500)
        except Exception:
            return _error("internal_error", status_code=500)

    def http_exception(_request: Request, error: Exception) -> Response:
        if isinstance(error, HTTPException) and error.status_code == 405:
            return _error("method_not_allowed", status_code=405)
        return _error("not_found", status_code=404)

    return Starlette(
        debug=False,
        routes=(
            Route("/api/v1/search-jobs", submit_job, methods=("POST",)),
            Route("/api/v1/search-jobs/{locator}", get_job, methods=("GET",)),
            Route(
                "/api/v1/search-jobs/{locator}/cancel",
                cancel_job,
                methods=("POST",),
            ),
            Route("/api/v1/search-history/{locator}", get_history, methods=("GET",)),
        ),
        exception_handlers={HTTPException: http_exception},
    )


__all__ = [
    "InMemoryProductionSubmissionStore",
    "ProductionSubmission",
    "SEARCH_SUBMISSION_HEADER",
    "SearchHistoryApiView",
    "SearchJobApiView",
    "create_local_production_api",
]
