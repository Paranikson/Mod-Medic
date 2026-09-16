# Mod Medic front end

One-page React app. Upload a workspace `.zip`; the FastAPI backend checks it.

## Run with the backend

From the project root, start the API:

```
pip install -r requirements.txt
uvicorn api:app --reload
```

In another terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://127.0.0.1:8000.
