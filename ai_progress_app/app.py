from ai_progress_app.db import init_db
from ai_progress_app.ui import build_app


def main():
    init_db()
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
