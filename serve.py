"""Production entrypoint for InsightReview's single-process job runner."""

from waitress import serve

import config
from app import app


if __name__ == "__main__":
    serve(
        app,
        host=config.HOST,
        port=config.PORT,
        threads=config.WEB_THREADS,
    )
