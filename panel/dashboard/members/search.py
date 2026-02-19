from flask import Blueprint, render_template

search_bp = Blueprint("search", __name__, url_prefix="/members/search")

@search_bp.route("/")
def search():
    return render_template("members/search.html")
