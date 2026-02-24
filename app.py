import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import gradio as gr

DATA_PATH = Path("data_store.json")

WEIGHTS = {
    "sleep": 25,
    "protein": 20,
    "workout": 20,
    "steps": 15,
    "water": 10,
    "mood": 5,
    "consistency": 5,
}

RANK_THRESHOLDS = [
    (85, "Platinum"),
    (70, "Gold"),
    (50, "Silver"),
    (0, "Bronze"),
]


DEFAULT_STORE = {
    "profile": None,
    "daily_logs": [],
}


def load_store() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return DEFAULT_STORE.copy()

    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "profile" not in data:
        data["profile"] = None
    if "daily_logs" not in data:
        data["daily_logs"] = []
    return data


def save_store(store: Dict[str, Any]) -> None:
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def date_key(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def get_streak(daily_logs: List[Dict[str, Any]], current_date: str) -> int:
    if not daily_logs:
        return 0

    dates = sorted({log["date"] for log in daily_logs})
    target = date_key(current_date)
    if current_date not in dates:
        return 0

    streak = 0
    seen = set(dates)
    while target.strftime("%Y-%m-%d") in seen:
        streak += 1
        target = target.fromordinal(target.toordinal() - 1)
    return streak


def clamp_ratio(value: float, goal: float) -> float:
    if goal <= 0:
        return 0.0
    return max(0.0, min(value / goal, 1.0))


def rank_for_score(score: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if score >= threshold:
            return rank
    return "Bronze"


def compute_score(profile: Dict[str, Any], metrics: Dict[str, Any], streak: int) -> Dict[str, Any]:
    goals = profile["goals"]

    ratios = {
        "sleep": clamp_ratio(metrics["sleep_hours"], goals["sleep_hours"]),
        "protein": clamp_ratio(metrics["protein_grams"], goals["protein_grams"]),
        "workout": 1.0 if metrics["workout_completed"] else 0.0,
        "steps": clamp_ratio(metrics["steps"], goals["steps_per_day"]),
        "water": clamp_ratio(metrics["water_liters"], goals["water_liters"]),
        "mood": max(0.0, min((metrics["mood"] - 1) / 4, 1.0)),
        "consistency": max(0.0, min(streak / 7, 1.0)),
    }

    contributions = {k: round(WEIGHTS[k] * ratios[k], 2) for k in WEIGHTS}
    raw_score = sum(contributions.values())
    total_score = max(0, min(100, round(raw_score)))

    return {
        "total_score": total_score,
        "rank_tier": rank_for_score(total_score),
        "contributions": contributions,
        "normalized_ratios": ratios,
    }


def save_profile(
    email: str,
    display_name: str,
    units: str,
    sleep_hours: float,
    protein_grams: float,
    workouts_per_week: int,
    steps_per_day: int,
    water_liters: float,
) -> str:
    if not email or not display_name:
        return "Please provide both email and display name."

    store = load_store()
    store["profile"] = {
        "id": "local-user",
        "email": email.strip(),
        "display_name": display_name.strip(),
        "created_at": datetime.utcnow().isoformat(),
        "units": units,
        "goals": {
            "sleep_hours": float(sleep_hours),
            "protein_grams": float(protein_grams),
            "workouts_per_week": int(workouts_per_week),
            "steps_per_day": int(steps_per_day),
            "water_liters": float(water_liters),
        },
    }
    save_store(store)
    return "✅ Profile saved successfully."


def submit_daily_checkin(
    date: str,
    sleep_hours: float,
    protein_grams: float,
    workout_completed: bool,
    steps: int,
    water_liters: float,
    mood: int,
    journal_text: str,
) -> str:
    store = load_store()
    profile = store.get("profile")
    if not profile:
        return "⚠️ Please save your profile first in the Onboarding tab."

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    metrics = {
        "sleep_hours": float(sleep_hours),
        "protein_grams": float(protein_grams),
        "workout_completed": bool(workout_completed),
        "steps": int(steps),
        "water_liters": float(water_liters),
        "mood": int(mood),
    }

    existing_logs = [log for log in store["daily_logs"] if log["date"] != date]
    streak = get_streak(existing_logs + [{"date": date}], date)
    score_breakdown = compute_score(profile, metrics, streak)

    log = {
        "id": f"local-user-{date}",
        "user_id": "local-user",
        "date": date,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "journal_text": journal_text.strip(),
        "score_breakdown": score_breakdown,
    }

    store["daily_logs"] = sorted(existing_logs + [log], key=lambda x: x["date"])
    save_store(store)

    contrib = score_breakdown["contributions"]
    return (
        f"✅ Check-in saved for {date}\n\n"
        f"Score: **{score_breakdown['total_score']}** ({score_breakdown['rank_tier']})\n"
        f"Sleep {contrib['sleep']}/25 | Protein {contrib['protein']}/20 | "
        f"Workout {contrib['workout']}/20 | Steps {contrib['steps']}/15 | "
        f"Water {contrib['water']}/10 | Mood {contrib['mood']}/5 | "
        f"Consistency {contrib['consistency']}/5"
    )


def render_history() -> str:
    store = load_store()
    profile = store.get("profile")
    daily_logs = store.get("daily_logs", [])

    if not profile:
        return "No profile found yet. Complete onboarding first."

    if not daily_logs:
        return "No daily logs yet. Submit your first check-in."

    lines = [
        f"### {profile['display_name']}'s Check-in History",
        "",
        "| Date | Score | Rank | Sleep | Protein | Workout | Steps | Water | Mood |",
        "|---|---:|---|---:|---:|---|---:|---:|---:|",
    ]

    for log in sorted(daily_logs, key=lambda x: x["date"], reverse=True):
        m = log["metrics"]
        s = log["score_breakdown"]
        lines.append(
            f"| {log['date']} | {s['total_score']} | {s['rank_tier']} | {m['sleep_hours']}h | "
            f"{m['protein_grams']}g | {'Yes' if m['workout_completed'] else 'No'} | "
            f"{m['steps']} | {m['water_liters']}L | {m['mood']} |"
        )

    return "\n".join(lines)


def build_app() -> gr.Blocks:
    today_default = datetime.now().strftime("%Y-%m-%d")

    with gr.Blocks(title="AI Progress MVP Prototype") as demo:
        gr.Markdown("# AI Journaling + Progress Tracker (MVP Prototype)")
        gr.Markdown("Use the tabs to set goals, log daily habits, and review score history.")

        with gr.Tab("Onboarding"):
            email = gr.Textbox(label="Email")
            display_name = gr.Textbox(label="Display Name")
            units = gr.Radio(["metric", "imperial"], value="metric", label="Units")
            sleep_goal = gr.Number(label="Sleep Goal (hours)", value=8)
            protein_goal = gr.Number(label="Protein Goal (grams)", value=140)
            workout_goal = gr.Number(label="Workouts per Week", value=4, precision=0)
            steps_goal = gr.Number(label="Steps Goal (per day)", value=8000, precision=0)
            water_goal = gr.Number(label="Water Goal (liters)", value=2.5)
            save_profile_btn = gr.Button("Save Profile")
            onboarding_status = gr.Markdown()

            save_profile_btn.click(
                fn=save_profile,
                inputs=[
                    email,
                    display_name,
                    units,
                    sleep_goal,
                    protein_goal,
                    workout_goal,
                    steps_goal,
                    water_goal,
                ],
                outputs=onboarding_status,
            )

        with gr.Tab("Daily Check-in"):
            checkin_date = gr.Textbox(label="Date (YYYY-MM-DD)", value=today_default)
            sleep_hours = gr.Number(label="Sleep (hours)", value=8)
            protein_grams = gr.Number(label="Protein (grams)", value=120)
            workout_completed = gr.Checkbox(label="Workout Completed", value=False)
            steps = gr.Number(label="Steps", value=7000, precision=0)
            water_liters = gr.Number(label="Water (liters)", value=2.0)
            mood = gr.Slider(1, 5, value=3, step=1, label="Mood")
            journal_text = gr.Textbox(label="Journal Entry", lines=5, placeholder="How did today go?")
            submit_btn = gr.Button("Submit Check-in")
            checkin_status = gr.Markdown()

            submit_btn.click(
                fn=submit_daily_checkin,
                inputs=[
                    checkin_date,
                    sleep_hours,
                    protein_grams,
                    workout_completed,
                    steps,
                    water_liters,
                    mood,
                    journal_text,
                ],
                outputs=checkin_status,
            )

        with gr.Tab("History"):
            refresh_btn = gr.Button("Refresh History")
            history_output = gr.Markdown()
            refresh_btn.click(fn=render_history, inputs=[], outputs=history_output)

    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
