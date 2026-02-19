from flask import Blueprint, render_template

roles_bp = Blueprint("roles", __name__, url_prefix="/moderation/roles")

@roles_bp.route("/")
def roles():
    return render_template("moderation/roles.html")
