diff --git a/README.md b/README.md
index f3432a189ecb400140037dacfac9f26dd094fcf5..41d5e844cd9d5cae82b1a375f6efc4c2ee3930f8 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,22 @@
 # ai-progress-app
+
+Simple Gradio MVP prototype for an AI journaling + progress tracking app.
+
+## Features
+- Onboarding profile + goals setup.
+- Daily check-in with validation and completeness rules.
+- Weighted scoring + rank tiers.
+- Heuristic AI insight (summary, tone, suggestion).
+- Progress view (7-day trend, streak, weekly averages, workouts this week).
+- Local JSON persistence in camelCase (`data_store.json`).
+
+## Run locally
+
+```bash
+python -m venv .venv
+source .venv/bin/activate
+pip install -r requirements.txt
+python app.py
+```
+
+Then open `http://localhost:7860`.
