# Campus Eats Android Kiosk

Customer-facing Android app using Jetpack Compose. It calls the Django API for vendors, menus, and orders. The AI chat uses the authenticated `/api/ai/parse-order/` endpoint and submits only after the user confirms the returned draft.

## Configure

1. Copy `local.properties.example` to `local.properties` in this directory.
2. For an Android emulator on the same computer as Django, set:

   ```properties
   api.base.url=http://10.0.2.2:8000/
   kiosk.username=YOUR_KIOSK_USERNAME
   kiosk.password=YOUR_KIOSK_PASSWORD
   ```

   For a physical device, use the computer's LAN IP and run Django bound to `0.0.0.0`; allow the port through the local firewall. Never commit `local.properties` or put the Groq/Supabase secrets in this app.
3. Start Django and Redis. The kiosk user must be able to obtain a JWT from `/api/auth/token/`. Groq is called only by Django.
4. Open this folder in Android Studio and run the `app` configuration, or use `gradlew.bat :app:assembleDebug`.

Debug builds allow cleartext HTTP for local development. Release builds disallow it and should use an HTTPS API URL.

## Text and voice ordering flow

1. The app creates a UUID session and sends each typed or recognized transcript to `POST /api/ai/parse-order/` with its JWT.
2. Android's configured speech-recognition service turns speech into editable text. This app sends the transcript, not audio, to Django; the recognizer itself may use a device-vendor service or network.
3. The app shows clarification questions for `ASK`/`REPAIR`, and keeps using the same session ID for follow-up turns.
4. For a valid `CONFIRM` result, the app displays the vendor, items, options, and delivery location. The user supplies a phone number or email.
5. Only after the user taps **Confirm and place order** does the app call `POST /api/orders/`, including `ai_session_id` and the signed `confirmation_token`.

The app does not contain a Groq API key or connect directly to Supabase/PostgreSQL.
