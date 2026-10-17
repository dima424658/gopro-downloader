"""HTTP route registration for the desktop application."""

from flask import Flask

from .camera import blueprint as camera_blueprint
from .local_media import blueprint as local_media_blueprint
from .media import blueprint as media_blueprint
from .pages import blueprint as pages_blueprint


def register_routes(app: Flask) -> None:
    """Register all application route groups."""
    app.register_blueprint(pages_blueprint)
    app.register_blueprint(camera_blueprint)
    app.register_blueprint(media_blueprint)
    app.register_blueprint(local_media_blueprint)
