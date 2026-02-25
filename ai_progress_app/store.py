from typing import Any, Optional

from .coach import detect_bottleneck, structure_goals
from .db import connection_scope
from .utils import now_iso


def get_profile(user_id: int):
    with connection_scope() as conn:
        return conn.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,)).fetchone()


def save_profile(user_id: int, display_name: str, photo_path: Optional[str] = None) -> str:
    if not display_name.strip():
        return 'Display name is required.'
    ts = now_iso()
    with connection_scope() as conn:
        existing = conn.execute('SELECT user_id FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
        if existing:
            conn.execute(
                'UPDATE profiles SET display_name = ?, photo_path = ?, updated_at = ?, onboarding_complete = 1 WHERE user_id = ?',
                (display_name.strip(), photo_path, ts, user_id),
            )
        else:
            conn.execute(
                '''
                INSERT INTO profiles (user_id, display_name, photo_path, onboarding_complete, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                ''',
                (user_id, display_name.strip(), photo_path, ts, ts),
            )
    return 'Profile saved.'


def save_broad_goals(user_id: int, raw_text: str) -> list[dict[str, str]]:
    text = (raw_text or '').strip()
    if not text:
        return []
    structured = structure_goals(text)
    ts = now_iso()

    with connection_scope() as conn:
        conn.execute('INSERT INTO broad_goals (user_id, raw_text, created_at) VALUES (?, ?, ?)', (user_id, text, ts))
        conn.execute('DELETE FROM structured_goals WHERE user_id = ?', (user_id,))
        conn.executemany(
            '''
            INSERT INTO structured_goals
            (user_id, category, measurable_habit, weekly_target, long_term_milestone, rationale, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    user_id,
                    goal['category'],
                    goal['measurable_habit'],
                    goal['weekly_target'],
                    goal['long_term_milestone'],
                    goal['rationale'],
                    ts,
                )
                for goal in structured
            ],
        )
    return structured


def get_structured_goals(user_id: int) -> list[dict[str, str]]:
    with connection_scope() as conn:
        rows = conn.execute(
            '''
            SELECT category, measurable_habit, weekly_target, long_term_milestone, rationale
            FROM structured_goals WHERE user_id = ? ORDER BY id ASC
            ''',
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_daily_log(
    user_id: int,
    date: str,
    sleep_hours: Optional[float],
    workouts: Optional[int],
    steps: Optional[int],
    protein_grams: Optional[float],
    water_liters: Optional[float],
    mood: Optional[int],
    journal_text: str,
) -> str:
    ts = now_iso()
    with connection_scope() as conn:
        conn.execute(
            '''
            INSERT INTO daily_logs
            (user_id, date, sleep_hours, workouts, steps, protein_grams, water_liters, mood, journal_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date)
            DO UPDATE SET
                sleep_hours = excluded.sleep_hours,
                workouts = excluded.workouts,
                steps = excluded.steps,
                protein_grams = excluded.protein_grams,
                water_liters = excluded.water_liters,
                mood = excluded.mood,
                journal_text = excluded.journal_text,
                updated_at = excluded.updated_at
            ''',
            (user_id, date, sleep_hours, workouts, steps, protein_grams, water_liters, mood, journal_text.strip(), ts, ts),
        )
    return f'Check-in saved for {date}.'


def dashboard_snapshot(user_id: int) -> dict[str, Any]:
    with connection_scope() as conn:
        profile = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
        goals = conn.execute(
            'SELECT category, measurable_habit, weekly_target, long_term_milestone, rationale FROM structured_goals WHERE user_id = ?',
            (user_id,),
        ).fetchall()
        latest = conn.execute(
            'SELECT * FROM daily_logs WHERE user_id = ? ORDER BY date DESC LIMIT 1',
            (user_id,),
        ).fetchone()
        recent = conn.execute(
            'SELECT date FROM daily_logs WHERE user_id = ? ORDER BY date DESC LIMIT 30',
            (user_id,),
        ).fetchall()

    metrics = {
        'sleep_hours': latest['sleep_hours'] if latest else 0,
        'workouts': latest['workouts'] if latest else 0,
        'steps': latest['steps'] if latest else 0,
        'protein_grams': latest['protein_grams'] if latest else 0,
        'water_liters': latest['water_liters'] if latest else 0,
        'mood': latest['mood'] if latest else 3,
    }
    bottleneck, suggestion = detect_bottleneck(metrics)

    streak = 0
    if recent:
        streak = min(len(recent), 30)

    energy = round(min(100, ((metrics['sleep_hours'] or 0) / 8) * 100))
    discipline = round(min(100, ((metrics['workouts'] or 0) / 1) * 100))
    consistency = round(min(100, streak / 14 * 100))
    health = round(min(100, ((metrics['water_liters'] or 0) / 2) * 100))
    focus = round(min(100, ((metrics['steps'] or 0) / 8000) * 100))

    return {
        'display_name': profile['display_name'] if profile else 'User',
        'stats': {
            'Energy': energy,
            'Discipline': discipline,
            'Consistency': consistency,
            'Health': health,
            'Focus': focus,
        },
        'metrics': metrics,
        'goals': [dict(row) for row in goals],
        'coach_card': {
            'bottleneck': bottleneck,
            'suggestion': suggestion,
        },
    }
