from datetime import datetime
from pathlib import Path
from typing import Optional

import gradio as gr

from .auth import get_user_for_session, logout, signup_or_login
from .coach import goals_to_markdown
from .db import init_db
from .store import (
    dashboard_snapshot,
    get_profile,
    get_structured_goals,
    save_broad_goals,
    save_profile,
    upsert_daily_log,
)

UPLOAD_DIR = Path('uploads')
UPLOAD_DIR.mkdir(exist_ok=True)


def _auth_guard(token: Optional[str]):
    user = get_user_for_session(token)
    if user is None:
        return None, 'Please login first.'
    return user, ''


def _save_profile(token: Optional[str], display_name: str, photo):
    user, err = _auth_guard(token)
    if err:
        return err, gr.update(visible=True), gr.update(visible=False)

    photo_path = None
    if photo:
        suffix = Path(photo).suffix or '.png'
        target = UPLOAD_DIR / f"user_{user['id']}{suffix}"
        Path(photo).replace(target)
        photo_path = str(target)

    status = save_profile(user['id'], display_name, photo_path)
    return status, gr.update(visible=False), gr.update(visible=True)


def _submit_goals(token: Optional[str], broad_goal_text: str):
    user, err = _auth_guard(token)
    if err:
        return err
    structured = save_broad_goals(user['id'], broad_goal_text)
    if not structured:
        return 'Please describe at least one broad goal.'
    return goals_to_markdown(structured)


def _save_checkin(token: Optional[str], date: str, sleep: float, workouts: int, steps: int, protein: float, water: float, mood: int, journal: str):
    user, err = _auth_guard(token)
    if err:
        return err
    return upsert_daily_log(user['id'], date, sleep, workouts, steps, protein, water, mood, journal)


def _render_dashboard(token: Optional[str]):
    user, err = _auth_guard(token)
    if err:
        return err
    snap = dashboard_snapshot(user['id'])
    lines = [f"## Welcome, {snap['display_name']}", '', '### Live Stats']
    for k, v in snap['stats'].items():
        lines.append(f'- **{k}:** {v}/100')

    m = snap['metrics']
    lines.extend(
        [
            '',
            '### Today\'s Inputs',
            f"- Sleep: {m['sleep_hours']}h",
            f"- Workouts: {m['workouts']}",
            f"- Steps: {m['steps']}",
            f"- Protein: {m['protein_grams']}g",
            f"- Water: {m['water_liters']}L",
            f"- Mood: {m['mood']}/5",
            '',
            '### Coach Card',
            f"- Main bottleneck: **{snap['coach_card']['bottleneck']}**",
            f"- Suggested action for tomorrow: {snap['coach_card']['suggestion']}",
        ]
    )
    return '\n'.join(lines)


def _login(email: str, password: str):
    token, msg = signup_or_login(email, password)
    if token is None:
        return None, msg, gr.update(visible=True), gr.update(visible=False)

    user = get_user_for_session(token)
    profile = get_profile(user['id']) if user else None
    show_profile_setup = profile is None or profile['onboarding_complete'] == 0
    return (
        token,
        msg,
        gr.update(visible=show_profile_setup),
        gr.update(visible=not show_profile_setup),
    )


def _logout(token: Optional[str]):
    msg = logout(token)
    return None, msg, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)


def _load_existing_goals(token: Optional[str]):
    user, err = _auth_guard(token)
    if err:
        return err
    return goals_to_markdown(get_structured_goals(user['id']))


def build_app():
    init_db()

    today = datetime.now().strftime('%Y-%m-%d')

    with gr.Blocks(title='AI Coaching + Progress App (Phase 1)', theme=gr.themes.Soft()) as demo:
        session_token = gr.State(value=None)

        gr.Markdown('# AI Journaling + Coaching App — Phase 1')
        gr.Markdown('Login/signup, profile setup, broad goals → AI-structured goals, and gamified dashboard stats.')

        auth_status = gr.Markdown('Please login or signup to continue.')

        with gr.Row():
            email = gr.Textbox(label='Email')
            password = gr.Textbox(label='Password', type='password')
            login_btn = gr.Button('Login / Signup')
            logout_btn = gr.Button('Logout')

        with gr.Group(visible=True) as profile_gate:
            gr.Markdown('## Profile Setup (required first time only)')
            display_name = gr.Textbox(label='Display name')
            photo = gr.File(label='Upload photo (stored for future avatar generation)', type='filepath')
            profile_btn = gr.Button('Save Profile & Continue')
            profile_status = gr.Markdown()

        with gr.Group(visible=False) as app_area:
            with gr.Tab('Goal Onboarding'):
                broad_goals = gr.Textbox(
                    label='Describe what you want to achieve in life right now',
                    lines=5,
                    placeholder='Be as broad or specific as you want.',
                )
                goals_btn = gr.Button('Generate Structured Goals')
                goals_out = gr.Markdown()
                refresh_goals_btn = gr.Button('Load Saved Goals')

            with gr.Tab('Daily Check-in'):
                date = gr.Textbox(label='Date', value=today)
                sleep = gr.Number(label='Sleep (hours)', value=0)
                workouts = gr.Number(label='Workouts today', value=0, precision=0)
                steps = gr.Number(label='Steps', value=0, precision=0)
                protein = gr.Number(label='Protein (grams)', value=0)
                water = gr.Number(label='Water (liters)', value=0)
                mood = gr.Number(label='Mood (1-5)', value=3, precision=0)
                journal = gr.Textbox(label='Journal', lines=4)
                save_checkin_btn = gr.Button('Save Check-in')
                checkin_out = gr.Markdown()

            with gr.Tab('Dashboard'):
                dash_btn = gr.Button('Refresh Dashboard')
                dash_out = gr.Markdown()

        login_btn.click(
            fn=_login,
            inputs=[email, password],
            outputs=[session_token, auth_status, profile_gate, app_area],
        )
        logout_btn.click(
            fn=_logout,
            inputs=[session_token],
            outputs=[session_token, auth_status, profile_gate, app_area, profile_status],
        )
        profile_btn.click(
            fn=_save_profile,
            inputs=[session_token, display_name, photo],
            outputs=[profile_status, profile_gate, app_area],
        )
        goals_btn.click(fn=_submit_goals, inputs=[session_token, broad_goals], outputs=[goals_out])
        refresh_goals_btn.click(fn=_load_existing_goals, inputs=[session_token], outputs=[goals_out])
        save_checkin_btn.click(
            fn=_save_checkin,
            inputs=[session_token, date, sleep, workouts, steps, protein, water, mood, journal],
            outputs=[checkin_out],
        )
        dash_btn.click(fn=_render_dashboard, inputs=[session_token], outputs=[dash_out])

    return demo
