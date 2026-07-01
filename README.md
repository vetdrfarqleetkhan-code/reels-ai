# REELS AI

REELS AI is a Streamlit application for creating vertical reels from a script, ordered images, voiceover, optional music, and synchronized captions.

## Run locally

Use Python 3.11:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>.

## Deploy on Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with GitHub.
2. Create an app from this repository.
3. Choose the `main` branch and set the entrypoint to `app.py`.
4. Select Python 3.11 and deploy.

Streamlit Cloud reads `requirements.txt`, `packages.txt`, and `.streamlit/config.toml` automatically. The Whisper transcription model downloads on the first timestamp-generation request.

See [DEPLOY.md](DEPLOY.md) for operational notes and the Docker fallback.
