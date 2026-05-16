"""
VeraBil — Flask Application Entry Point
"""

import os
from flask import Flask
from flask_cors import CORS

from config import Config
from routes.analyze import analyze_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/*": {"origins": "*"}})

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.register_blueprint(analyze_bp)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "VeraBil API", "version": "1.0.0"}

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=Config.DEBUG,
    )
