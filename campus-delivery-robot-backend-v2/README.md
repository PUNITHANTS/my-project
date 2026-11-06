# Campus Delivery Robot Backend

Django REST backend for the campus delivery application. Supabase PostgreSQL stores application data; Redis stores short-lived AI conversation state and powers Channels notifications. The robot integration is still a mock adapter and does not command a physical robot.

For a file-by-file code map and explanation of how the apps connect, see [`CODEBASE_GUIDE.md`](CODEBASE_GUIDE.md).

## Implemented workflow

```text
Student portal --JWT--> Django API
    |                       |-- Supabase PostgreSQL: accounts, vendors, menu, orders, dispatch, status history
    |                       |-- Redis: temporary conversation state and real-time channel layer
    |                       `-- Groq: text-to-structured-order interpretation (backend only)
    |
    `-- POST /api/ai/parse-order/ -> validated draft -> clarification/repair loop
                                      -> cart confirmation -> POST /api/orders/

Vendor portal --JWT--> menu availability/options and order lifecycle APIs
Admin portal  --JWT--> Django admin and management APIs
```

The conversational endpoint reads the live menu, checks availability and customization rules, preserves unedited cart lines, and returns a signed confirmation token only for a valid final cart. The order endpoint rechecks the current menu and requires that token for AI-created orders. C1-C5 are configurable clarification policies for the report experiments; C5 falls back to C3 until a classifier is trained.

## Local setup

1. Create and activate a virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env`. Fill in the Supabase database password, a strong `DJANGO_SECRET_KEY`, and a Groq API key. Set `GROQ_MODEL` to a model currently available to your Groq account. Keep all of these values in the backend environment; never put database credentials or the Groq key in frontend code.

3. Start Redis. `docker-compose.yml` starts Redis only; it does not create a local PostgreSQL database. If Docker is unavailable, install/use a Redis-compatible local service or configure a managed Redis URL in `REDIS_URL`.

4. Apply the additive migrations to your Supabase project and create a Django administrator:

   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```

   Use `makemigrations` only after you intentionally change Django models. These migrations add menu options/availability, AI experiment logs, and order status history; they do not drop existing application tables.

5. Run the API:

   ```powershell
   python manage.py runserver
   ```

   Check `http://127.0.0.1:8000/api/health/` and `http://127.0.0.1:8000/admin/`.

## Frontend API integration

Obtain JWT tokens from `POST /api/auth/token/`, then send `Authorization: Bearer <access-token>` for protected routes. Use the same UUID `session_id` across successive AI conversation turns:

```http
POST /api/ai/parse-order/
Content-Type: application/json
Authorization: Bearer <access-token>
```

```json
{
  "session_id": "a9c5e845-3ed7-49b7-a0ae-4797cba464d2",
  "transcript": "One veggie wrap and a lemonade, deliver to the library"
}
```

Use `action`, `clarificationNeeded`, `items`, `valid_for_submission`, and `confirmation_token` from the response. If the action is `ASK` or `REPAIR`, show the question and send the user's answer as the next transcript with the same session ID. On a valid `CONFIRM`, show the complete cart and obtain explicit user confirmation before creating an order. On `ESCALATE`, do not submit; direct the user to review the cart or contact the vendor. Never submit a cart merely because the AI returned a draft. Vendor menu create/update accepts nested `option_groups` and `availability_windows`; when either key is sent during an update, that full list replaces the existing list. Omit the key to leave it unchanged.

```http
POST /api/orders/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "student_name": "Student Name",
  "phone": "5551234567",
  "vendor_id": 4,
  "delivery_location": "Main Library",
  "items": [
    {"menu_item_id": 12, "quantity": 1, "customization": "Oat milk"}
  ],
  "ai_session_id": "a9c5e845-3ed7-49b7-a0ae-4797cba464d2",
  "confirmation_token": "<token returned by the final AI response>"
}
```

For a non-AI order, omit both `ai_session_id` and `confirmation_token`. Menu item IDs returned by the AI are strings representing the database IDs; send them as integers to the order API. Other core routes include `/api/vendors/`, `/api/menu/items/`, `/api/orders/`, `/api/orders/<id>/status/`, and `/api/dispatch/`.

## Report experiments

Create a frozen menu snapshot before annotating so menu IDs/options stay consistent:

```powershell
python manage.py export_menu_snapshot --output data/menu_snapshot_v1.json
```

Prepare JSONL dialogues as described in [`data/README.md`](data/README.md), then split by source group (not by individual turns) to avoid dialogue leakage:

```powershell
python manage.py split_dialogue_dataset --input data/dialogues.jsonl --output-dir data/splits
python manage.py run_conversation_experiments --input data/splits/train.jsonl --output-dir data/evaluations/train --menu-snapshot data/menu_snapshot_v1.json
python manage.py run_conversation_experiments --input data/splits/validation.jsonl --output-dir data/evaluations/validation --menu-snapshot data/menu_snapshot_v1.json
```

The runner writes per-policy metrics and derived feature JSONL files without transcripts. Train C5 using the train and validation feature files for C2, then run the held-out test experiment only after the threshold and model are fixed:

```powershell
python manage.py train_clarification_policy --train data/evaluations/train/c2_features.jsonl --validation data/evaluations/validation/c2_features.jsonl
python manage.py run_conversation_experiments --input data/splits/test.jsonl --output-dir data/evaluations/test --menu-snapshot data/menu_snapshot_v1.json
```

Set `AI_LOG_TURNS=True` only when you have an approved reason and appropriate consent/retention rules for transcript logging. Logs are off by default; use `export_ai_turn_logs` and `purge_ai_turn_logs --older-than-days N --confirm` only under your project's data-governance process.

## Safety and scope

- `.env` is ignored by Git; share `.env.example`, not real credentials. If a real Supabase password or API key was committed or shared, rotate it in the provider dashboard and remove it from Git history.
- Supabase's public/anon or service-role keys are not needed by this Django database connection. Frontends call Django, not PostgreSQL directly.
- Configure CORS for the exact local/deployed frontend origins.
- The current dispatch adapter records a mock robot acceptance. Physical robot credentials, navigation, payment processing, voice ordering, and production deployment are not implemented by this report-aligned backend change.
