"""
VeraBil — Flask Application Entry Point
"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from config import Config
from routes.analyze import analyze_bp

# Resolve the frontend directory relative to this file
_FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/*": {"origins": "*"}})

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.register_blueprint(analyze_bp)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "VeraBil API", "version": "1.0.0"}

    # ── Serve frontend static files ───────────────────────────
    @app.route("/")
    def index():
        return send_from_directory(_FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def frontend(filename):
        return send_from_directory(_FRONTEND_DIR, filename)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=Config.DEBUG,
    )
