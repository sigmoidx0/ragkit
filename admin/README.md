# ragkit admin

Vite + React + TypeScript SPA.

## Run

```bash
npm install
npm run dev
```

Dev server: http://localhost:5173 — `/api/*` is proxied to `http://localhost:8000`.

## Features

- Login / logout (`Authorization: Bearer …` stored in `localStorage`)
- Documents: list, upload, detail, download, preview, replace file, delete
- Search: semantic search (optional filter by document id)
- Members *(service admin+)*: add users to a service, change roles, remove members
- Services *(superadmin only)*: create and delete services
