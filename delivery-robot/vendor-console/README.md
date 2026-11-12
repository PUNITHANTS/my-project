# Vendor Console

This is the React/Vite vendor portal. For the overall project layout and the Android customer kiosk instructions, see [`../README.md`](../README.md).

## Run locally

Start Django from the repository root, then open a second PowerShell terminal in this folder:

```powershell
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Vite prints the local URL, normally `http://localhost:5173`. `.env.local` configures only the Django HTTP and WebSocket URLs; it must not contain Supabase or Groq credentials. Add the Vite origin to the backend's `CORS_ALLOWED_ORIGINS` setting if the browser blocks requests.

To verify a production bundle, run `npm run build`.
