from flask import Flask
from routes.dashboard import dashboard_bp
from routes.members.search import search_bp
from routes.members.levels import levels_bp
from routes.members.economy import economy_bp
from routes.moderation.prison import prison_bp
from routes.moderation.warn import warn_bp
from routes.moderation.logs import logs_bp
from routes.moderation.roles import roles_bp
from routes.configuration.commands import commands_bp
from routes.configuration.permissions import permissions_bp
from routes.configuration.security import security_bp
from routes.statistics import statistics_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = "super_secret_key"

    # Register Blueprints
    app.register_blueprint(dashboard_bp)

    app.register_blueprint(search_bp)
    app.register_blueprint(levels_bp)
    app.register_blueprint(economy_bp)

    app.register_blueprint(prison_bp)
    app.register_blueprint(warn_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(roles_bp)

    app.register_blueprint(commands_bp)
    app.register_blueprint(permissions_bp)
    app.register_blueprint(security_bp)

    app.register_blueprint(statistics_bp)

    return app
