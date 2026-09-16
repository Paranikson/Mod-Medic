# Mod Medic

Checks an MCreator workspace for common student mistakes. Instructors and campers upload a `.zip`; the app reports missing textures, broken links, and similar problems in plain language.

## Run the backend and frontend together

Use two terminals from the project root.

**1. Backend**

```
pip install -r requirements.txt
uvicorn api:app --reload
```

This serves the API at http://127.0.0.1:8000.

**2. Frontend**

```
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173). In development, `/api` requests are proxied to the backend, so you do not need to change CORS.

Export a workspace from MCreator with **File → Export workspace to ZIP**, then drop that file on the page.
