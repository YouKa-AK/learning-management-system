from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)

    # Enable SQLite foreign keys
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    #  IMPORT MODELS HERE (CRITICAL)
    from app.models.user import User
    from app.models.course import Course
    from app.models.enrollment import Enrollment

    # Register blueprints
    from app.routes.course_routes import course_bp
    app.register_blueprint(course_bp)

    # Create tables
    with app.app_context():
        db.create_all()

    return app
