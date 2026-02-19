from flask import Blueprint, render_template

security_bp = Blueprint("security", __name__, url_prefix="/configuration/security")

@security_bp.route("/")
def security():
    return render_template("configuration/security.html")
security.html
