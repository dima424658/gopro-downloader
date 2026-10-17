"""Flask and pywebview components for the GoPro desktop application."""

from __future__ import annotations

from flask import Flask

from .resources import RESOURCE_DIR


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=RESOURCE_DIR / "templates",
        static_folder=RESOURCE_DIR / "static",
    )
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

    from .jobs import job_routes
    from .routes import register_routes

    app.register_blueprint(job_routes)
    register_routes(app)
    return app
