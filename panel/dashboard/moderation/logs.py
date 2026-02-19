from flask import Blueprint, render_template

logs_bp = Blueprint("logs", __name__, url_prefix="/moderation/logs")

@logs_bp.route("/")
def logs():
    return render_template("moderation/logs.html")
