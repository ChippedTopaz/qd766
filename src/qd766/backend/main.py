from __future__ import annotations

import uvicorn

from .app import create_app

app = create_app()


def run() -> None:
    uvicorn.run("qd766.backend.main:app", host="127.0.0.1", port=8767, reload=False)


if __name__ == "__main__":
    run()
