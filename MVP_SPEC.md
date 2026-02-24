# AI Journaling + Progress Tracking App (MVP Spec)

## 1) MVP Goal (1–2 week build)
Ship a mobile-first web app where a user logs a short daily journal + core health habits, gets an AI summary, and receives a transparent daily score with a simple rank tier (Bronze/Silver/Gold/Platinum). The MVP optimizes for **daily consistency**, not clinical accuracy.

Success criteria for MVP:
- User can complete a daily log in under 2 minutes.
- User sees a score breakdown and understands why the score changed.
- User can view trend over last 7 days and current rank tier.

---

## 2) Core Features (MVP only)

1. **Authentication (basic)**
   - Email + password or passwordless magic link.
   - User has one profile with goals + preferred units.

2. **Daily Log Entry**
   - Inputs for date, sleep hours, protein grams, workouts completed, steps, water, mood (1–5), short free-text journal.
   - Allow save/edit for current day (and optional past day correction).

3. **AI Journal Insight (lightweight)**
   - Generate a short response from journal text:
     - `summary` (1–2 sentences)
     - `tone` (positive/neutral/stressed)
     - `one suggestion` for tomorrow
   - Keep it simple and non-medical.

4. **Daily Score + Rank**
   - Compute a 0–100 score from habit metrics using explicit weights.
   - Show per-metric contribution (e.g., Sleep: 18/25).
   - Map score to rank tier.

5. **Progress Views**
   - Last 7 days score trend (line/bar).
   - Streak count (consecutive days with submitted log).
   - Basic metric averages (sleep, steps, protein).

---

## 3) Screens (MVP)

1. **Onboarding/Profile Setup**
   - Name, age range (optional), units (metric/imperial), step goal, protein goal, sleep target, workout goal.

2. **Today Log Screen (primary)**
   - Fast form with habit inputs + journal text.
   - “Save log” CTA.
   - If already saved today: “Update log.”

3. **Daily Result Screen**
   - Total score (0–100).
   - Rank tier badge.
   - Score breakdown by metric.
   - AI summary + suggestion.

4. **Progress Screen**
   - 7-day chart.
   - Current streak.
   - Mini cards for weekly averages.

5. **Profile/Goals Screen**
   - Edit targets and preferences.

Navigation can be a simple bottom tab: **Today / Progress / Profile**.

---

## 4) Data Model (TypeScript interfaces)

```ts
export type RankTier = "Bronze" | "Silver" | "Gold" | "Platinum";

export interface UserProfile {
  id: string;
  email: string;
  displayName: string;
  createdAt: string; // ISO timestamp
  units: "metric" | "imperial";

  // User-configurable goals
  goals: {
    sleepHours: number;      // e.g., 8
    proteinGrams: number;    // e.g., 140
    workoutsPerWeek: number; // e.g., 4
    stepsPerDay: number;     // e.g., 8000
    waterLiters: number;     // e.g., 2.5
  };

  // Optional personalization knobs
  scoringPreferences?: {
    prioritizeRecovery?: boolean;
    prioritizePerformance?: boolean;
  };
}

export interface Metric {
  key:
    | "sleep"
    | "protein"
    | "workout"
    | "steps"
    | "water"
    | "mood"
    | "consistency";
  label: string;
  value: number;
  goal?: number;
  unit?: string;
}

export interface ScoreBreakdown {
  date: string; // YYYY-MM-DD
  totalScore: number; // 0-100
  rankTier: RankTier;

  // Weighted point contributions (already scaled)
  contributions: {
    sleep: number;
    protein: number;
    workout: number;
    steps: number;
    water: number;
    mood: number;
    consistency: number;
  };

  // Helpful for UI transparency/debugging
  normalizedRatios: {
    sleep: number;       // 0-1
    protein: number;     // 0-1
    workout: number;     // 0-1
    steps: number;       // 0-1
    water: number;       // 0-1
    mood: number;        // 0-1
    consistency: number; // 0-1
  };

  aiInsight?: {
    summary: string;
    tone: "positive" | "neutral" | "stressed";
    suggestion: string;
  };
}

export interface DailyLog {
  id: string;
  userId: string;
  date: string; // YYYY-MM-DD
  createdAt: string; // ISO timestamp
  updatedAt: string; // ISO timestamp

  metrics: {
    sleepHours: number;
    proteinGrams: number;
    workoutCompleted: boolean;
    steps: number;
    waterLiters: number;
    mood: 1 | 2 | 3 | 4 | 5;
  };

  journalText: string;

  // Derived fields (can also be computed on read)
  scoreBreakdown?: ScoreBreakdown;
}
```

---

## 5) Scoring + Ranking Algorithm Proposal

### Metric weights (sum = 100)
- Sleep: **25**
- Protein: **20**
- Workout: **20**
- Steps: **15**
- Water: **10**
- Mood: **5**
- Consistency/Streak bonus: **5**

### Normalization rules (0–1 each)
- `sleepRatio = min(sleepHours / sleepGoal, 1)`
- `proteinRatio = min(proteinGrams / proteinGoal, 1)`
- `workoutRatio = workoutCompleted ? 1 : 0`
- `stepsRatio = min(steps / stepsGoal, 1)`
- `waterRatio = min(waterLiters / waterGoal, 1)`
- `moodRatio = (mood - 1) / 4`
- `consistencyRatio = min(currentStreak / 7, 1)`

### Daily score formula
```ts
score =
  25 * sleepRatio +
  20 * proteinRatio +
  20 * workoutRatio +
  15 * stepsRatio +
  10 * waterRatio +
   5 * moodRatio +
   5 * consistencyRatio;

finalScore = Math.round(Math.max(0, Math.min(100, score)));
```

### Rank tiers
- **Bronze:** 0–49
- **Silver:** 50–69
- **Gold:** 70–84
- **Platinum:** 85–100

### Why this works for MVP
- Transparent and easy to explain in UI.
- Encourages balanced behavior, not just one strong metric.
- Can be tuned later without schema changes.

---

## 6) Assumptions

1. Single-user profile context (no teams/social features in MVP).
2. Daily logging is manual; no wearables integration yet.
3. AI insight is optional per save and can be async.
4. No medical claims or diagnosis; app is habit coaching only.
5. Goals are user-defined, and scoring is relative to goals.
6. Missing metric values default to `0` for scoring unless user saves partial draft behavior explicitly.
7. Timezone is based on user profile or device; one log per user per day.
8. MVP prioritizes web app delivery over native mobile apps.
