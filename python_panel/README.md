# PulsePanel Python

Petit panel web Python base sur Flask avec login admin et connexion a un bot Discord existant.

## Installation

```powershell
cd python_panel
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

## Variables

- `FLASK_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `DISCORD_CLIENT_ID`

## URL

Le panel tourne ensuite sur `http://127.0.0.1:5000`.
