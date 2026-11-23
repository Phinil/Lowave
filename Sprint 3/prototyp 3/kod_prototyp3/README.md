# Smallweb Smaller Artists App

En tidig kodversion (prototyp 3) där:

- `spotify_tracks.csv` är datasetbasen för filtrering och rekommendationslogik
- Deezer används för artistbilder, previews, ISRC-uppslag och topplåtar
- Last.fm används för lyssnarsiffror, bio och liknande artister
- sparade och egeninlagda artister återanvänds i flöde och rekommendationer

## Projektstruktur

- `backend/app/main.py`: FastAPI-app och API-endpoints
- `backend/app/recommendations.py`: rekommendationsmotor och logik för mindre artister
- `backend/app/dataset.py`: inläsning och aggregering av Spotify-datasetet
- `backend/app/external_services.py`: Deezer- och Last.fm-anrop med cache
- `backend/app/storage.py`: lokal persistens för sparade artister, egna tillskott och community-inlägg
- `frontend/index.html`: appens HTML-skal
- `frontend/app.js`: SPA-logik, navigation och rendering
- `frontend/styles.css`: Figma-inspirerad styling
- `data/spotify_tracks.csv`: kopia av datasetet
- `data/user_state.json`: skapas automatiskt när appen körs

## Kör lokalt

1. Gå till projektmappen:

```powershell
cd "Sprint 3/prototyp 3/kod_prototyp3"
```

2. Skapa och aktivera en virtuell miljö:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. Installera backend-beroenden:

```powershell
pip install -r backend\requirements.txt
```

4. Skapa `.env` från `.env.example` och fyll i din `LASTFM_API_KEY`.

5. Starta appen:

```powershell
uvicorn backend.app.main:app --reload
```

6. Öppna:

```text
http://127.0.0.1:8000
```

## Antaganden

- Deezer används utan API-nyckel eftersom deras öppna sökendpoints räcker för den här appen.
- Om Last.fm saknas eller svarar långsamt kan appen fortfarande fungera med datasetet och Deezer, men resultatkvaliteten blir lägre.
- År i promptar används som en mjuk filtrering och används bara när Deezer-data innehåller ett släppår.
