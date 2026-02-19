from flask import Blueprint, render_template

prison_bp = Blueprint("prison", __name__, url_prefix="/moderation/prison")

@prison_bp.route("/")
def prison():
    return render_template("moderation/prison.html")
