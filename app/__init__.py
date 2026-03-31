import os
from flask import Flask
from app.extensions import db

def create_app():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(BASE_DIR, 'templates')
    )

    app.config.from_object("config.Config")

    db.init_app(app)

    # Register blueprints
    from app.routes.course_routes import course_bp
    app.register_blueprint(course_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    return app
