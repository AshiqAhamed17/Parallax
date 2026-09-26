"""Top-level entrypoint for the Parallax public API (Phase 13).

The application lives in `parallax_research.api` (so it ships with the `research` uv project and is
covered by the same `uv run ruff` / `uv run pytest` tooling). This thin shim re-exports it so the
service can be run from the repo root:

    uvicorn api.main:app --reload           # serve
    PARALLAX_DB=data/parallax.db uvicorn api.main:app

`create_app(db_path)` is available for building an app against a specific database.
"""

from parallax_research.api import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
