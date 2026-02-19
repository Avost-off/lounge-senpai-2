from flask import Blueprint, render_template

warn_bp = Blueprint("warn", __name__, url_prefix="/moderation/warn")

@warn_bp.route("/")
def warn():
    return render_template("moderation/warn.html")
