# ai-progress-app

Simple Gradio MVP prototype for an AI journaling + progress tracking app.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:7860`.

## Data storage

The app stores onboarding profile + daily check-ins in `data_store.json` in the project root.
