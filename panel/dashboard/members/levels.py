from flask import Blueprint, render_template

levels_bp = Blueprint("levels", __name__, url_prefix="/members/levels")

@levels_bp.route("/")
def levels():
    return render_template("members/levels.html")
