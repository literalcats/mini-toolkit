# Mini Toolkit

Five small Python tools in one Flask app, themed dark gray + forest green.

- Compute age and days
- Electricity calculator
- Grade boundary checker
- Largest of three numbers
- Secret number game

## Run locally

    pip install -r requirements.txt
    python app.py

Open http://127.0.0.1:5000

## Deploy to Render

1. Push this folder to a GitHub repo.
2. On render.com: New -> Web Service -> connect the repo.
3. Settings: Runtime Python, Build Command `pip install -r requirements.txt`,
   Start Command `gunicorn app:app`, Instance type Free.
   (Or use New -> Blueprint, which reads render.yaml automatically.)
4. Add env var SECRET_KEY = any long random text (Blueprint does this for you).
5. Deploy. Your site is at https://<name>.onrender.com

Note: free instances sleep after ~15 min idle, so the first visit may take ~30-60 s.
