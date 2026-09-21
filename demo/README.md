# UML Assessment Demo

Minimal browser UI for generating, editing, and assessing Use Case Diagrams.

## Run

Start the API from the repository root:

```sh
uv run uvicorn src.controller.api.app:app --reload
```

Then start the frontend:

```sh
cd demo
cp .env.example .env
# Set VITE_API_KEY to the same value as the backend API_SECRET.
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The frontend uses the Vite `/api` proxy, so no backend CORS change is required.
The compatible Apollon v3 package is pinned because the assessment API accepts
the v3 `elements`/`relationships` model.
