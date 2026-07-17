import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from config import Config


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.home"
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth_routes import auth
    from app.main_routes import main

    app.register_blueprint(auth)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        from app.seed import seed_reference_data

        seed_reference_data()

    return app
