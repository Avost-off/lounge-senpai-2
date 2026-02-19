from flask import Blueprint, render_template

permissions_bp = Blueprint("permissions", __name__, url_prefix="/configuration/permissions")

@permissions_bp.route("/")
def permissions():
    return render_template("configuration/permissions.html")
