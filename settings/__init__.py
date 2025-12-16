from flask import Blueprint

bp = Blueprint("settings", __name__, url_prefix="/api/settings")

from . import routes  # noqa: F401
