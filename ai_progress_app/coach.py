from typing import Any

CATEGORY_KEYWORDS = {
    'fitness': ['workout', 'fitness', 'exercise', 'weight', 'run', 'health', 'strength'],
    'productivity': ['career', 'work', 'focus', 'productivity', 'business', 'study', 'project'],
    'mental_health': ['stress', 'anxiety', 'calm', 'meditation', 'mindset', 'mental'],
    'relationships': ['family', 'friends', 'relationship', 'partner', 'social'],
    'finance': ['money', 'finance', 'saving', 'income', 'debt', 'invest'],
}


def structure_goals(raw_text: str) -> list[dict[str, str]]:
    text = (raw_text or '').strip()
    if not text:
        return []

    lowered = text.lower()
    picked: list[str] = []
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in lowered for word in words):
            picked.append(category)

    if not picked:
        picked = ['productivity', 'mental_health']

    goals: list[dict[str, str]] = []
    for cat in picked[:3]:
        if cat == 'fitness':
            goals.append(
                {
                    'category': 'fitness',
                    'measurable_habit': 'Move your body for at least 20 minutes.',
                    'weekly_target': '4 sessions per week',
                    'long_term_milestone': 'Sustain an active routine for 12 weeks',
                    'rationale': 'Physical activity boosts energy and supports consistency in other goals.',
                }
            )
        elif cat == 'productivity':
            goals.append(
                {
                    'category': 'productivity',
                    'measurable_habit': 'Do one 45-minute deep-work block daily.',
                    'weekly_target': '5 deep-work blocks per week',
                    'long_term_milestone': 'Complete one meaningful project milestone every month',
                    'rationale': 'Focused effort compounds into measurable life progress.',
                }
            )
        elif cat == 'mental_health':
            goals.append(
                {
                    'category': 'mental_health',
                    'measurable_habit': 'Take a 10-minute decompression or mindfulness break.',
                    'weekly_target': '6 days per week',
                    'long_term_milestone': 'Report lower stress and better mood trends over 8 weeks',
                    'rationale': 'Stress management protects follow-through on all other habits.',
                }
            )
        elif cat == 'relationships':
            goals.append(
                {
                    'category': 'relationships',
                    'measurable_habit': 'Reach out intentionally to one person each day.',
                    'weekly_target': '5 meaningful check-ins per week',
                    'long_term_milestone': 'Build a stable support network over 3 months',
                    'rationale': 'Strong relationships increase resilience and motivation.',
                }
            )
        elif cat == 'finance':
            goals.append(
                {
                    'category': 'finance',
                    'measurable_habit': 'Track spending and save a fixed amount weekly.',
                    'weekly_target': 'Review finances 2 times per week',
                    'long_term_milestone': 'Reach a savings target within 6 months',
                    'rationale': 'Financial clarity reduces stress and improves long-term options.',
                }
            )
    return goals


def detect_bottleneck(metrics: dict[str, Any]) -> tuple[str, str]:
    candidates = {
        'sleep': (metrics.get('sleep_hours') or 0) / 8,
        'workouts': (metrics.get('workouts') or 0) / 1,
        'steps': (metrics.get('steps') or 0) / 8000,
        'protein': (metrics.get('protein_grams') or 0) / 120,
        'water': (metrics.get('water_liters') or 0) / 2,
        'mood': ((metrics.get('mood') or 3) - 1) / 4,
    }
    key = min(candidates, key=candidates.get)
    fix = {
        'sleep': 'Set a hard wind-down alarm 60 minutes before bed.',
        'workouts': 'Do the 8-minute minimum workout right after waking up.',
        'steps': 'Take one 10-minute walk after lunch.',
        'protein': 'Anchor breakfast with one protein source.',
        'water': 'Finish one full bottle before noon.',
        'mood': 'Do a 3-minute breathing reset when stress spikes.',
    }[key]
    return key, fix


def goals_to_markdown(goals: list[dict[str, str]]) -> str:
    if not goals:
        return 'No structured goals generated yet.'
    lines = ['### AI-Structured Goals']
    for i, goal in enumerate(goals, start=1):
        lines.extend(
            [
                f"{i}. **{goal['category'].replace('_', ' ').title()}**",
                f"   - Habit: {goal['measurable_habit']}",
                f"   - Weekly target: {goal['weekly_target']}",
                f"   - Long-term milestone: {goal['long_term_milestone']}",
                f"   - Why this matters: {goal['rationale']}",
            ]
        )
    return '\n'.join(lines)
