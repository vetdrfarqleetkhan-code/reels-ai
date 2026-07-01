# Deploy REELS AI

## Easiest option: Streamlit Community Cloud

1. Create a new GitHub repository and upload this project. Do not upload `.venv`, `temp`, `output`, `projects`, or the downloaded Whisper model; `.gitignore` already excludes them.
2. Sign in at <https://share.streamlit.io> with GitHub and select **Create app**.
3. Select the repository and branch, and set the main file path to `app.py`.
4. In **Advanced settings**, choose **Python 3.11**, then deploy.
5. Wait for the build to finish and open the public `streamlit.app` URL.

The first click on **Generate timestamps** downloads the transcription model, so it will take longer than later runs. Cloud storage is temporary; users should download finished reels instead of relying on saved drafts.

## Heavier option: Render with Docker

Use this if Community Cloud runs out of memory while rendering.

1. Push this project to GitHub.
2. At <https://dashboard.render.com>, select **New > Blueprint**.
3. Connect the repository. Render detects `render.yaml` and builds the included `Dockerfile`.
4. Choose an instance with at least 2 GB RAM. The free 512 MB service is not enough for transcription plus video rendering.

Render assigns the public URL automatically. The health check is `/_stcore/health`.

## Important privacy note

This app stores current uploads and generated videos on the server filesystem. Deploy it privately or for trusted, low-traffic use unless per-user isolated storage and authentication are added.
