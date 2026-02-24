import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_PATH = Path("data_store.json")
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_METRICS_FOR_COMPLETE = 3

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

DEFAULT_STORE = {"profile": None, "dailyLogs": []}


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def parse_date(value: str) -> Optional[datetime]:
    if not value or not DATE_REGEX.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def load_store() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return DEFAULT_STORE.copy()

    try:
        raw = DATA_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return DEFAULT_STORE.copy()
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_STORE.copy()

    if not isinstance(data, dict):
        return DEFAULT_STORE.copy()

    # Migration layer to camelCase if older snake_case data exists.
    if "dailyLogs" not in data and "daily_logs" in data:
        data["dailyLogs"] = data.pop("daily_logs")

    profile = data.get("profile")
    if isinstance(profile, dict):
        if "display_name" in profile:
            profile["displayName"] = profile.pop("display_name")
        if "created_at" in profile:
            profile["createdAt"] = profile.pop("created_at")

        goals = profile.get("goals")
        if isinstance(goals, dict):
            key_map = {
                "sleep_hours": "sleepHours",
                "protein_grams": "proteinGrams",
                "workouts_per_week": "workoutsPerWeek",
                "steps_per_day": "stepsPerDay",
                "water_liters": "waterLiters",
            }
            for old, new in key_map.items():
                if old in goals:
                    goals[new] = goals.pop(old)

    migrated_logs: List[Dict[str, Any]] = []
    logs = data.get("dailyLogs")
    if not isinstance(logs, list):
        logs = []

    for raw_log in logs:
        if not isinstance(raw_log, dict):
            continue
        log = dict(raw_log)

        if "user_id" in log:
            log["userId"] = log.pop("user_id")
        if "created_at" in log:
            log["createdAt"] = log.pop("created_at")
        if "updated_at" in log:
            log["updatedAt"] = log.pop("updated_at")
        if "journal_text" in log:
            log["journalText"] = log.pop("journal_text")
        if "score_breakdown" in log:
            log["scoreBreakdown"] = log.pop("score_breakdown")

        metrics = log.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        metric_map = {
            "sleep_hours": "sleepHours",
            "protein_grams": "proteinGrams",
            "workout_completed": "workoutCompleted",
            "water_liters": "waterLiters",
        }
        for old, new in metric_map.items():
            if old in metrics:
                metrics[new] = metrics.pop(old)

        # Safe defaults for legacy/partial logs.
        log["metrics"] = metrics
        log["scoreBreakdown"] = log.get("scoreBreakdown") if isinstance(log.get("scoreBreakdown"), dict) else {}
        if "isComplete" not in log:
            log["isComplete"] = True

        migrated_logs.append(log)

    data["dailyLogs"] = migrated_logs
    if "profile" not in data:
        data["profile"] = None
    return data


def save_store(store: Dict[str, Any]) -> None:
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)


def clamp_ratio(value: float, goal: float) -> float:
    if goal <= 0:
        return 0.0
    return max(0.0, min(value / goal, 1.0))


def rank_for_score(score: int) -> str:
    for threshold, rank in RANK_THRESHOLDS:
        if score >= threshold:
            return rank
    return "Bronze"


def clean_number(value: Any, name: str, integer: bool = False) -> Tuple[Optional[float], Optional[str]]:
    if value is None or value == "":
        return None, None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, f"{name} must be a number."
    if numeric < 0:
        return None, f"{name} cannot be negative."
    if integer and not numeric.is_integer():
        return None, f"{name} must be a whole number."
    return (int(numeric) if integer else numeric), None


def metrics_provided_count(metrics: Dict[str, Any]) -> int:
    count = 0
    for key in ["sleepHours", "proteinGrams", "steps", "waterLiters", "mood"]:
        if metrics.get(key) is not None:
            count += 1
    if metrics.get("workoutCompleted"):
        count += 1
    return count


def is_log_complete(metrics: Dict[str, Any], journal_text: str) -> bool:
    return bool(journal_text.strip()) or metrics_provided_count(metrics) >= MIN_METRICS_FOR_COMPLETE


def completed_dates(logs: List[Dict[str, Any]]) -> set:
    dates = set()
    for log in logs:
        if not isinstance(log, dict):
            continue
        if not log.get("isComplete"):
            continue
        d = log.get("date")
        if isinstance(d, str) and parse_date(d):
            dates.add(d)
    return dates


def get_streak(logs: List[Dict[str, Any]], target_date: str) -> int:
    target = parse_date(target_date)
    if not target:
        return 0
    done_dates = completed_dates(logs)
    streak = 0
    while date_str(target) in done_dates:
        streak += 1
        target -= timedelta(days=1)
    return streak


def generate_ai_insight(
    journal_text: str,
    mood: Optional[int],
    contributions: Dict[str, float],
    normalized_ratios: Optional[Dict[str, float]] = None,
) -> Dict[str, str]:
    journal = journal_text.strip()
    lowered = journal.lower()

    if journal:
        sentence = re.split(r"(?<=[.!?])\s+", journal)[0].strip()
        summary = sentence if sentence else journal[:140]
    else:
        summary = "No journal entry added today."

    positive_words = ["good", "great", "happy", "calm", "energized", "productive"]
    stressed_words = ["stress", "anxious", "overwhelmed", "tired", "exhausted", "bad"]

    mood_value = mood if mood is not None else 3
    if mood_value <= 2 or any(word in lowered for word in stressed_words):
        tone = "stressed"
    elif mood_value >= 4 or any(word in lowered for word in positive_words):
        tone = "positive"
    else:
        tone = "neutral"

    candidate_metrics = ["sleep", "protein", "workout", "steps", "water", "mood"]
    target_metric = None
    if isinstance(normalized_ratios, dict):
        ratio_candidates = {k: normalized_ratios.get(k) for k in candidate_metrics}
        usable = {k: v for k, v in ratio_candidates.items() if isinstance(v, (int, float))}
        if usable:
            min_ratio = min(usable.values())
            tied = [k for k, v in usable.items() if v == min_ratio]
            # Tie-safe deterministic selection, not relying on first metric ordering.
            target_metric = sorted(tied)[-1]

    if target_metric is None:
        target_metric = min(
            candidate_metrics,
            key=lambda metric: contributions.get(metric, 0.0) / WEIGHTS[metric],
        )

    suggestion_map = {
        "sleep": "Try a wind-down routine tonight to protect your sleep target.",
        "protein": "Plan one protein-focused meal ahead for tomorrow.",
        "workout": "Schedule a short workout block on your calendar for tomorrow.",
        "steps": "Add a 10-minute walk after one meal tomorrow.",
        "water": "Keep a water bottle nearby and finish one full refill by noon.",
        "mood": "Take 5 minutes for reflection or breathing before bed.",
    }

    return {"summary": summary, "tone": tone, "suggestion": suggestion_map[target_metric]}


def compute_score(profile: Dict[str, Any], metrics: Dict[str, Any], streak: int) -> Dict[str, Any]:
    goals = profile.get("goals")
    if not isinstance(goals, dict):
        zero = {k: 0 for k in WEIGHTS}
        return {
            "totalScore": 0,
            "rankTier": "Bronze",
            "contributions": dict(zero),
            "normalizedRatios": dict(zero),
        }

    sleep = metrics.get("sleepHours") or 0.0
    protein = metrics.get("proteinGrams") or 0.0
    steps = metrics.get("steps") or 0
    water = metrics.get("waterLiters") or 0.0
    mood = metrics.get("mood") if metrics.get("mood") is not None else 3

    ratios = {
        "sleep": clamp_ratio(sleep, goals["sleepHours"]),
        "protein": clamp_ratio(protein, goals["proteinGrams"]),
        "workout": 1.0 if metrics.get("workoutCompleted") else 0.0,
        "steps": clamp_ratio(float(steps), goals["stepsPerDay"]),
        "water": clamp_ratio(water, goals["waterLiters"]),
        "mood": max(0.0, min((mood - 1) / 4, 1.0)),
        "consistency": max(0.0, min(streak / 7, 1.0)),
    }
    contributions = {k: round(WEIGHTS[k] * ratios[k], 2) for k in WEIGHTS}
    total_score = max(0, min(100, round(sum(contributions.values()))))

    return {
        "totalScore": total_score,
        "rankTier": rank_for_score(total_score),
        "contributions": contributions,
        "normalizedRatios": ratios,
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
        "displayName": display_name.strip(),
        "createdAt": now_iso(),
        "units": units,
        "goals": {
            "sleepHours": float(sleep_hours),
            "proteinGrams": float(protein_grams),
            "workoutsPerWeek": int(workouts_per_week),
            "stepsPerDay": int(steps_per_day),
            "waterLiters": float(water_liters),
        },
    }
    save_store(store)
    return "✅ Profile saved successfully."


def submit_daily_checkin(
    date: str,
    sleep_hours: Optional[float],
    protein_grams: Optional[float],
    workout_completed: bool,
    steps: Optional[float],
    water_liters: Optional[float],
    mood: Optional[float],
    journal_text: str,
) -> str:
    store = load_store()
    profile = store.get("profile")
    if not profile:
        return "⚠️ Please save your profile first in the Onboarding tab."

    input_date = date.strip() if date else date_str(datetime.now())
    if not parse_date(input_date):
        return "⚠️ Date must be in YYYY-MM-DD format."

    sleep_val, err = clean_number(sleep_hours, "Sleep")
    if err:
        return f"⚠️ {err}"
    protein_val, err = clean_number(protein_grams, "Protein")
    if err:
        return f"⚠️ {err}"
    steps_val, err = clean_number(steps, "Steps", integer=True)
    if err:
        return f"⚠️ {err}"
    water_val, err = clean_number(water_liters, "Water")
    if err:
        return f"⚠️ {err}"
    mood_val, err = clean_number(mood, "Mood", integer=True)
    if err:
        return f"⚠️ {err}"
    if mood_val is not None:
        mood_val = max(1, min(5, int(mood_val)))

    metrics = {
        "sleepHours": sleep_val,
        "proteinGrams": protein_val,
        "workoutCompleted": bool(workout_completed),
        "steps": steps_val,
        "waterLiters": water_val,
        "mood": mood_val,
    }

    complete = is_log_complete(metrics, journal_text)
    if not complete:
        return (
            "⚠️ Check-in is incomplete. Add a journal entry or provide at least "
            f"{MIN_METRICS_FOR_COMPLETE} metrics."
        )

    existing_logs = [log for log in store.get("dailyLogs", []) if isinstance(log, dict) and log.get("date") != input_date]
    draft_log = {"date": input_date, "isComplete": complete}
    streak = get_streak(existing_logs + [draft_log], input_date)

    score_breakdown = compute_score(profile, metrics, streak)
    ai_insight = generate_ai_insight(
        journal_text,
        metrics.get("mood"),
        score_breakdown.get("contributions", {}),
        score_breakdown.get("normalizedRatios", {}),
    )
    score_breakdown["aiInsight"] = ai_insight

    existing = next(
        (log for log in store.get("dailyLogs", []) if isinstance(log, dict) and log.get("date") == input_date),
        None,
    )
    created_at = (existing.get("createdAt") if isinstance(existing, dict) else None) or now_iso()

    log = {
        "id": f"local-user-{input_date}",
        "userId": "local-user",
        "date": input_date,
        "createdAt": created_at,
        "updatedAt": now_iso(),
        "metrics": metrics,
        "journalText": journal_text.strip(),
        "isComplete": complete,
        "scoreBreakdown": score_breakdown,
    }

    store["dailyLogs"] = sorted(existing_logs + [log], key=lambda x: x.get("date", ""))
    save_store(store)

    contrib = score_breakdown["contributions"]
    return (
        f"✅ Check-in saved for {input_date}\n\n"
        f"Score: **{score_breakdown['totalScore']}** ({score_breakdown['rankTier']})\n"
        f"Sleep {contrib['sleep']}/25 | Protein {contrib['protein']}/20 | Workout {contrib['workout']}/20\n"
        f"Steps {contrib['steps']}/15 | Water {contrib['water']}/10 | Mood {contrib['mood']}/5 | "
        f"Consistency {contrib['consistency']}/5\n\n"
        f"AI Insight ({ai_insight['tone']}): {ai_insight['summary']}\n"
        f"Suggestion: {ai_insight['suggestion']}"
    )


def _seven_day_scores(logs: List[Dict[str, Any]], today: datetime) -> List[Tuple[str, int]]:
    score_map = {}
    for log in logs:
        if not isinstance(log, dict):
            continue
        day = log.get("date")
        if not isinstance(day, str):
            continue
        score_breakdown = log.get("scoreBreakdown") or {}
        if not isinstance(score_breakdown, dict):
            score_breakdown = {}
        score = score_breakdown.get("totalScore", 0)
        try:
            score_map[day] = int(score)
        except (TypeError, ValueError):
            score_map[day] = 0

    output: List[Tuple[str, int]] = []
    for idx in range(6, -1, -1):
        day = date_str(today - timedelta(days=idx))
        output.append((day, int(score_map.get(day, 0))))
    return output


def render_progress() -> str:
    store = load_store()
    profile = store.get("profile")
    logs = store.get("dailyLogs", [])
    if not isinstance(logs, list):
        logs = []
    if not profile:
        return "No profile found yet. Complete onboarding first."

    today = datetime.now()
    today_key = date_str(today)
    streak = get_streak(logs, today_key)
    trend = _seven_day_scores(logs, today)

    def bar(score: int) -> str:
        filled = max(0, min(20, round(score / 5)))
        return "█" * filled + "░" * (20 - filled)

    recent_logs = []
    for log in logs:
        if not isinstance(log, dict):
            continue
        d = parse_date(log.get("date", ""))
        if d and d >= today - timedelta(days=6):
            recent_logs.append(log)
    metric_logs = [log for log in recent_logs if log.get("isComplete")]

    def avg(field: str) -> float:
        values = []
        for log in metric_logs:
            metrics = log.get("metrics") or {}
            if not isinstance(metrics, dict):
                continue
            v = metrics.get(field)
            if v is not None:
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    pass
        return round(sum(values) / len(values), 2) if values else 0.0

    start_of_week = today - timedelta(days=today.weekday())
    week_start = datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    week_logs = []
    for log in logs:
        if not isinstance(log, dict):
            continue
        d = parse_date(log.get("date", ""))
        if d and d >= week_start:
            week_logs.append(log)

    workouts_done = 0
    for log in week_logs:
        metrics = log.get("metrics") or {}
        if not isinstance(metrics, dict):
            continue
        if log.get("isComplete") is True and metrics.get("workoutCompleted") is True:
            workouts_done += 1

    workout_goal = profile.get("goals", {}).get("workoutsPerWeek", 0)

    lines = [
        f"### {profile.get('displayName', 'User')}'s Progress",
        "",
        f"**Current completed-day streak:** {streak}",
        f"**Workouts this week:** {workouts_done}/{workout_goal}",
        "",
        "#### Last 7 days score trend",
    ]

    for day, score in trend:
        lines.append(f"- {day}: {score:>3} {bar(score)}")

    lines.extend(
        [
            "",
            "#### Weekly averages (completed logs only)",
            f"- Sleep: {avg('sleepHours')} hours",
            f"- Steps: {avg('steps')}",
            f"- Protein: {avg('proteinGrams')} g",
            f"- Water: {avg('waterLiters')} L",
        ]
    )
    return "\n".join(lines)


def render_history() -> str:
    store = load_store()
    profile = store.get("profile")
    daily_logs = store.get("dailyLogs", [])
    if not isinstance(daily_logs, list):
        daily_logs = []

    if not profile:
        return "No profile found yet. Complete onboarding first."
    if not daily_logs:
        return "No daily logs yet. Submit your first check-in."

    lines = [
        f"### {profile.get('displayName', 'User')}'s Check-in History",
        "",
        "| Date | Complete | Score | Rank | Sleep | Protein | Workout | Steps | Water | Mood |",
        "|---|---|---:|---|---:|---:|---|---:|---:|---:|",
    ]

    def log_sort_key(entry: Dict[str, Any]) -> str:
        return entry.get("date", "") if isinstance(entry, dict) else ""

    for log in sorted(daily_logs, key=log_sort_key, reverse=True):
        if not isinstance(log, dict):
            continue
        metrics = log.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        score_breakdown = log.get("scoreBreakdown") or {}
        if not isinstance(score_breakdown, dict):
            score_breakdown = {}

        date_value = log.get("date", "-")
        is_complete = "Yes" if log.get("isComplete") else "No"
        score = score_breakdown.get("totalScore", "-")
        rank = score_breakdown.get("rankTier", "-")

        lines.append(
            f"| {date_value} | {is_complete} | {score} | {rank} | "
            f"{metrics.get('sleepHours') if metrics.get('sleepHours') is not None else '-'} | "
            f"{metrics.get('proteinGrams') if metrics.get('proteinGrams') is not None else '-'} | "
            f"{'Yes' if metrics.get('workoutCompleted') else 'No'} | "
            f"{metrics.get('steps') if metrics.get('steps') is not None else '-'} | "
            f"{metrics.get('waterLiters') if metrics.get('waterLiters') is not None else '-'} | "
            f"{metrics.get('mood') if metrics.get('mood') is not None else '-'} |"
        )
    return "\n".join(lines)


def build_app():
    import gradio as gr

    today_default = date_str(datetime.now())

    with gr.Blocks(title="AI Progress MVP Prototype") as demo:
        gr.Markdown("# AI Journaling + Progress Tracker (MVP Prototype)")
        gr.Markdown("Set your goals, submit complete daily check-ins, and review progress.")

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
                inputs=[email, display_name, units, sleep_goal, protein_goal, workout_goal, steps_goal, water_goal],
                outputs=onboarding_status,
            )

        with gr.Tab("Daily Check-in"):
            checkin_date = gr.Textbox(label="Date (YYYY-MM-DD)", value=today_default)
            sleep_hours = gr.Number(label="Sleep (hours)", value=None)
            protein_grams = gr.Number(label="Protein (grams)", value=None)
            workout_completed = gr.Checkbox(label="Workout Completed", value=False)
            steps = gr.Number(label="Steps", value=None)
            water_liters = gr.Number(label="Water (liters)", value=None)
            mood = gr.Number(label="Mood (1-5)", value=None, precision=0)
            journal_text = gr.Textbox(label="Journal Entry", lines=5, placeholder="How did today go?")
            gr.Markdown(
                f"**Completeness rule:** journal text is non-empty OR at least {MIN_METRICS_FOR_COMPLETE} metrics are provided."
            )
            submit_btn = gr.Button("Submit Check-in")
            checkin_status = gr.Markdown()

            submit_btn.click(
                fn=submit_daily_checkin,
                inputs=[checkin_date, sleep_hours, protein_grams, workout_completed, steps, water_liters, mood, journal_text],
                outputs=checkin_status,
            )

        with gr.Tab("Progress"):
            refresh_progress_btn = gr.Button("Refresh Progress")
            progress_output = gr.Markdown()
            refresh_progress_btn.click(fn=render_progress, inputs=[], outputs=progress_output)

        with gr.Tab("History"):
            refresh_btn = gr.Button("Refresh History")
            history_output = gr.Markdown()
            refresh_btn.click(fn=render_history, inputs=[], outputs=history_output)

    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
