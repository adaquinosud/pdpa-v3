"""Flask app principal — PDPA v3."""

from flask import Flask
from flask_cors import CORS

from src.api.coleta import coleta_bp
from src.api.empresas import empresas_bp
from src.config import get_config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    CORS(app)

    app.register_blueprint(empresas_bp)
    app.register_blueprint(coleta_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "version": "3.0.0-dev"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
