"""Executable entry point."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "marketplace_auth.service:create_service",
        factory=True,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()

