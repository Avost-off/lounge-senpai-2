from flask import Blueprint, render_template

commands_bp = Blueprint("commands", __name__, url_prefix="/configuration/commands")

@commands_bp.route("/")
def commands():
    return render_template("configuration/commands.html")
