from flask import Blueprint, render_template

economy_bp = Blueprint("economy", __name__, url_prefix="/members/economy")

@economy_bp.route("/")
def economy():
    return render_template("members/economy.html")
