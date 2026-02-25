import os
from pathlib import Path

DB_PATH = Path(os.getenv('APP_DB_PATH', 'app.db'))
SESSION_TTL_HOURS = int(os.getenv('SESSION_TTL_HOURS', '168'))
