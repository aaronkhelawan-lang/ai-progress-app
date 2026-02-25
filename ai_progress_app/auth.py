import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from .config import SESSION_TTL_HOURS
from .db import connection_scope
from .utils import now_iso


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f'{salt}:{password}'.encode('utf-8')).hexdigest()


def signup_or_login(email: str, password: str) -> tuple[Optional[str], str]:
    email = (email or '').strip().lower()
    if not email or not password:
        return None, 'Email and password are required.'

    with connection_scope() as conn:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user is None:
            salt = secrets.token_hex(16)
            pwd_hash = _hash_password(password, salt)
            conn.execute(
                'INSERT INTO users (email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?)',
                (email, pwd_hash, salt, now_iso()),
            )
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            msg = 'Account created. You are now logged in.'
        else:
            expected = _hash_password(password, user['password_salt'])
            if expected != user['password_hash']:
                return None, 'Invalid credentials.'
            msg = 'Welcome back. Logged in successfully.'

        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat(timespec='seconds')
        conn.execute(
            'INSERT OR REPLACE INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)',
            (token, user['id'], expires, now_iso()),
        )
        return token, msg


def get_user_for_session(token: Optional[str]):
    if not token:
        return None
    with connection_scope() as conn:
        row = conn.execute(
            '''
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            ''',
            (token, now_iso()),
        ).fetchone()
        return row


def logout(token: Optional[str]) -> str:
    if not token:
        return 'Logged out.'
    with connection_scope() as conn:
        conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
    return 'Logged out.'
