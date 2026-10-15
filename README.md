# Mini Toolkit

Five small Python tools in one Flask app, themed dark gray + forest green.

- Compute age and days
- Electricity calculator
- Grade boundary checker
- Largest of three numbers
- Secret number game (stateless, so it works on serverless)

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deploy to Vercel

Vercel detects `app.py` with a Flask `app` object automatically.

```bash
npm i -g vercel
vercel          # preview
vercel --prod   # production
```

Or push this folder to GitHub and import the repo in the Vercel dashboard.

Optional: set a `SECRET_KEY` environment variable in Vercel (Project Settings -> Environment Variables)
so the secret-number tokens are signed with your own key.

## Structure

```
app.py               Flask app + API routes
templates/index.html UI (HTML, CSS, JS)
requirements.txt
```
