# GeoJSON Utility — Frontend

Vite + React + TypeScript frontend for the [geojson-utility](../README.md) app. Lets a signed-in user upload a CSV of locations, watch it get processed against the [backend API](../backend/README.md), and download the result with computed catchment-area GeoJSON.

## Stack

- [Vite](https://vitejs.dev/) + React 18 + TypeScript
- [Tailwind CSS](https://tailwindcss.com/) with a [shadcn/ui](https://ui.shadcn.com/) (Radix UI) component set in `src/components/ui`
- [Ant Design](https://ant.design/) for a few components (e.g. the login modal) and `styled-components` for some legacy pages — the codebase currently mixes these with shadcn/Tailwind
- `axios` for API calls, `eventsource` for streaming CSV processing status, `react-router-dom`, `@tanstack/react-query`

## Prerequisites

- Node.js 20+ (matches the version used in `Dockerfile`)
- A running instance of the [backend API](../backend/README.md)

## Setup

1. **Install dependencies:**
   ```sh
   npm install
   ```
2. **Configure the backend URL** — create a `.env` file in `frontend/`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
3. **Start the dev server:**
   ```sh
   npm run dev
   ```
   The app runs at `http://localhost:8080` (see `server.port` in `vite.config.ts`) and proxies API calls directly to `VITE_API_BASE_URL`.

### Scripts

| Command           | Purpose                                      |
| ------------------ | ----------------------------------------------- |
| `npm run dev`        | Start the Vite dev server with HMR                |
| `npm run build`       | Production build to `dist/`                       |
| `npm run build:dev`   | Build in development mode (unminified, for debugging) |
| `npm run preview`     | Preview a production build locally                  |
| `npm run lint`        | Run ESLint                                          |

### Docker

`Dockerfile` builds the app and serves the static output with [`serve`](https://www.npmjs.com/package/serve) on port 80. `VITE_API_BASE_URL` is baked in at build time via a Docker build arg (see the root [`docker-compose.yml`](../docker-compose.yml), which maps it to host port `7000`).

## Project structure

```
src/
├── pages/            # Route-level views (Index = landing/upload flow, Dashboard, NotFound)
├── components/        # LoginModal, StepContent (CSV upload/status flow), styled-components wrappers
├── components/ui/      # shadcn/Radix UI primitives (button, dialog, form, etc.)
├── contexts/           # AuthContext — holds the JWT and current user, backed by localStorage
├── hooks/               # use-mobile, use-toast
├── types/                # Shared TS types (auth.ts)
└── lib/                   # Utility helpers (cn/className merge, etc.)
```

## Auth flow

There's no self-service signup in the UI — a user receives a token out-of-band and pastes it into the **Sign In** modal (`components/LoginModal.tsx`), which calls `POST /auth/login` on the backend to validate it. On success, the JWT is stored in `localStorage` via `AuthContext` (`contexts/AuthContext.tsx`) and sent as `Authorization: Bearer <token>` on subsequent API calls. Live CSV-processing status (`components/StepContent.tsx`) is streamed over SSE, authenticated with a SHA-256 hash of the token passed as a query param (since `EventSource` can't send custom headers).

## Deploying

See the root [README](../README.md#quick-start-docker-compose) for running the full stack (frontend + backend + Postgres) via Docker Compose.
