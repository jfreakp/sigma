"""
Tests for the catch-all unhandled-exception handler registered in app/main.py.

This project's binding constraint is that ALL error responses use the shape
{"detail": ..., "error_code": "..."}. Before this handler existed, an
unhandled exception fell through to Starlette's default ServerErrorMiddleware
handling, which returns a plain-text "Internal Server Error" body instead of
that JSON shape.

To exercise this without adding a permanent debug route to the production
app, this test temporarily overrides the `get_db` dependency (the same
dependency-override mechanism already used by the `client`/`db_session`
fixtures in tests/conftest.py) with a callable that raises a bare Exception
instead of yielding a session, then hits a real endpoint that depends on it
(`POST /api/v1/auth/token`, which requires no auth itself), and clears the
override afterward so later tests are unaffected.

Note: this test builds its own httpx AsyncClient (rather than reusing the
shared `client` fixture) with `raise_app_exceptions=False`. Starlette's
ServerErrorMiddleware always re-raises the original exception after sending
the handler's response ("allows test clients to optionally raise the error
within the test case") - httpx's ASGITransport defaults to re-raising that
exception into the test (`raise_app_exceptions=True`), which is the right
default for catching accidental unhandled exceptions in other tests, but
would defeat the purpose of *this* test, which deliberately triggers one and
needs to inspect the resulting HTTP response instead.
"""

from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.main import app


async def test_unhandled_exception_returns_project_error_shape():
    async def raise_unhandled_error():
        raise RuntimeError("simulated unhandled exception for 500 test")

    app.dependency_overrides[get_db] = raise_unhandled_error
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/token",
                json={"client_id": "whoever", "client_secret": "whatever"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
