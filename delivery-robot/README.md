# Delivery Robot Applications

This folder mirrors the team's component layout:

- `android-kiosk/`: customer-facing Android app for menus, typed orders, and device-transcribed voice orders.
- `backend/`: Django API. Django Admin is served at `http://127.0.0.1:8000/admin/`.
- `vendor-console/`: React/Vite vendor portal for menu and order operations.

Both frontends call Django. Do not put Supabase database credentials or the Groq API key in either frontend.

## React vendor console

Start Django from `backend/` first. Then, in a separate PowerShell terminal opened at the workspace root:

```powershell
Set-Location .\delivery-robot\vendor-console
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Vite prints its local URL, normally `http://localhost:5173`. `.env.local` contains only Django HTTP and WebSocket base URLs. If the backend rejects browser requests, add the exact Vite origin to `CORS_ALLOWED_ORIGINS` in `delivery-robot/backend/.env` and restart Django.

## Android customer kiosk

Open `delivery-robot/android-kiosk` in Android Studio. Its `local.properties` is machine-specific and ignored by Git; keep the existing file. If it is missing, copy `local.properties.example` to `local.properties` and set `api.base.url`, `kiosk.username`, and `kiosk.password` for a dedicated low-privilege kiosk account. For an emulator, use `http://10.0.2.2:8000/` as the API base URL. For a physical kiosk/device, use the development computer's LAN address, bind Django to `0.0.0.0`, and allow the port through the firewall. Never put Supabase or Groq credentials in the Android app.

Android voice input is transcribed by the device's configured recognition service into editable text. Django/Groq receives the transcript, not raw audio. Verify a Gradle build and an end-to-end kiosk order before considering the app tested.
