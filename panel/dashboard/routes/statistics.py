from flask import Blueprint, render_template

statistics_bp = Blueprint("statistics", __name__, url_prefix="/statistics")

@statistics_bp.route("/")
def statistics():
    return render_template("statistics/index.html")
