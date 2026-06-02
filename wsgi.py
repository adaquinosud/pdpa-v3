"""WSGI entrypoint de produção (CP-deploy-2).

gunicorn serve este callable módulo-nível: ``gunicorn wsgi:app``. ``create_app()``
não recebe args e lê ``FLASK_ENV`` do ambiente (em produção → ``ProductionConfig``
+ boot-check do ``FLASK_SECRET_KEY``, ver CP-#4 segurança-código).

O ``__main__`` de dev (``app.run`` em ``src/app.py``) segue intacto para
desenvolvimento local — este arquivo é só o ponto de entrada de produção.
"""

from src.app import create_app

app = create_app()
