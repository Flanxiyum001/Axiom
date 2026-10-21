"""Small per-process request limits for the constrained public demo.

These limits protect one API process. A public host must also enforce limits at
its trusted ingress and run one worker, as documented in docs/judge-demo.md.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import BoundedSemaphore, Lock

from axiom.demo import DEMO_OBJECTIVE
from axiom.domain.interfaces import MemoryRepository
from axiom.domain.models import ResearchObjective
from fastapi import HTTPException, Request
from starlette.responses import PlainTextResponse

MAX_DEMO_OBJECTIVES = 100
MAX_MUTATIONS_PER_MINUTE = 30
MAX_MUTATIONS_PER_CLIENT_MINUTE = 6
MAX_DEMO_BODY_BYTES = 2048
MAX_DEMO_BODY_CHUNKS = 16


class DemoGuard:
    def __init__(self) -> None:
        self._lock = Lock()
        self._run_slot = BoundedSemaphore(1)
        self._global_times: deque[float] = deque()
        self._client_times: dict[str, deque[float]] = defaultdict(deque)

    def _admit(self, request: Request) -> None:
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        while self._global_times and now - self._global_times[0] >= 60:
            self._global_times.popleft()
        for old_client, times in list(self._client_times.items()):
            if not times or now - times[-1] >= 60:
                del self._client_times[old_client]
        client_times = self._client_times[client]
        while client_times and now - client_times[0] >= 60:
            client_times.popleft()
        if (
            len(self._global_times) >= MAX_MUTATIONS_PER_MINUTE
            or len(client_times) >= MAX_MUTATIONS_PER_CLIENT_MINUTE
        ):
            raise HTTPException(
                status_code=429, detail="Demo request limit reached; retry in a minute"
            )
        self._global_times.append(now)
        client_times.append(now)

    def create_objective(
        self,
        request: Request,
        repository: MemoryRepository,
        objective: ResearchObjective,
    ) -> None:
        if objective.description != DEMO_OBJECTIVE:
            raise HTTPException(
                status_code=422,
                detail="Demo accepts only the displayed fixed objective",
            )
        with self._lock:
            self._admit(request)
            if len(repository.list_objectives()) >= MAX_DEMO_OBJECTIVES:
                raise HTTPException(
                    status_code=429,
                    detail="Demo capacity reached; ask the owner to reset it",
                )
            repository.save_objective(objective)

    def begin_run(self, request: Request) -> None:
        with self._lock:
            self._admit(request)
            if not self._run_slot.acquire(blocking=False):
                raise HTTPException(
                    status_code=429, detail="A demo run is already in progress"
                )

    def end_run(self) -> None:
        self._run_slot.release()


class DemoBodyLimitMiddleware:
    """Read at most a small JSON body before forwarding a demo POST request."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > MAX_DEMO_BODY_BYTES or len(chunks) >= MAX_DEMO_BODY_CHUNKS:
                await PlainTextResponse(
                    "Demo request body is too large", status_code=413
                )(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        payload = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)
