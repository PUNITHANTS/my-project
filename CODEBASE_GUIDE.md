# Project Codebase Guide

The active application tree is `delivery-robot/`, with `android-kiosk/`, `backend/`, and `vendor-console/` as sibling components. This guide explains the backend application areas, their main files, and how requests flow. Paths such as `apps/...` and `config/...` below are relative to `delivery-robot/backend/`. `__init__.py` files are Python package markers; most contain no application logic. Migration files describe database schema changes and are summarized separately below. See `delivery-robot/README.md` for the customer, vendor, and admin interfaces.

## How The Parts Connect

```text
Android kiosk or React vendor console
  | HTTP + JWT
  v
config/urls.py -> app urls.py -> view -> serializer -> model/service -> Supabase PostgreSQL
                                      |
                                      +-> Redis for AI conversation sessions
                                      +-> Groq for structured text interpretation
                                      +-> Channels/Redis for order update events

Android system speech recognition -> editable text transcript -> Django AI endpoint
```

The Android kiosk is the customer interface, and the React app is the vendor interface. Django Admin at `/admin/` is the admin interface. Android's configured speech recognizer creates editable text; the backend receives text, not raw microphone audio. The frontends call Django and do not connect directly to Supabase or Groq.

## Project Entry And Configuration

- `manage.py`: Django command-line entry point. `main()` selects `config.settings` and passes commands such as `migrate` and `runserver` to Django.
- `config/settings.py`: Registers Django and project apps; configures Supabase PostgreSQL, custom user model, JWT defaults, CORS, Redis cache/Channels, Groq settings, AI policy thresholds, and Django's timezone.
- `config/urls.py`: Main HTTP route table. It exposes admin, health check, JWT token/refresh, accounts, vendors, menu, orders, dispatch, and AI routes. `healthcheck()` returns a simple status response.
- `config/asgi.py`: ASGI entry point. Sends HTTP to Django and WebSocket traffic through authentication middleware and `apps.notifications.routing`.
- `config/wsgi.py`: WSGI entry point for traditional synchronous hosting; WebSockets require the ASGI entry point.
- `delivery-robot/backend/.env.example`: Safe template for local environment variables. Copy to `delivery-robot/backend/.env` and fill in private values; do not commit `.env`.
- Root `.gitignore`: Excludes local secrets, virtual environments, Python caches, and generated AI/data artifacts from new Git tracking.
- `delivery-robot/backend/requirements.txt`: Python dependencies, including Django/DRF, PostgreSQL, Channels/Redis, Pydantic, and scikit-learn.
- `delivery-robot/backend/docker-compose.yml`: Starts Redis only. It does not start PostgreSQL; the configured database is Supabase.
- Root `README.md`: Setup, API examples, and report experiment commands.
- `delivery-robot/README.md`: Frontend roles and run instructions for Android and React.
- `delivery-robot/backend/data/README.md`: Annotated dialogue JSONL format and data-splitting guidance.

## Accounts And Permissions

- `apps/accounts/models.py`: Defines the custom Django `User`, adding `role` (student/vendor/admin/superadmin) and `phone` fields.
- `apps/accounts/serializers.py`: `UserSerializer` controls which profile fields are returned by the API.
- `apps/accounts/views.py`: `MeView.get_object()` returns the authenticated user for the current-user endpoint.
- `apps/accounts/urls.py`: Maps `/api/accounts/me/` to `MeView`.
- `apps/accounts/permissions.py`: `is_project_admin()` centralizes admin-role detection. `AdminOrManagedVendorWrite.has_permission()` allows authenticated reads and privileged writes; `has_object_permission()` limits vendor-object writes to its manager or an admin.
- `apps/accounts/admin.py`: Integrates the custom user model with Django admin.
- `apps/accounts/apps.py`: Django app registration metadata.

## Vendors

- `apps/vendors/models.py`: `Vendor` stores name, pickup/location label, active/intake-paused flags, and the optional manager user.
- `apps/vendors/serializers.py`: `VendorSerializer` maps vendor fields to API JSON.
- `apps/vendors/views.py`: `VendorViewSet.get_queryset()` supports vendor discovery. `perform_create()` restricts vendor creation to admins. `perform_update()` prevents a vendor manager from reassigning ownership.
- `apps/vendors/urls.py`: Registers list/detail CRUD routes with a DRF router; write permissions are enforced by `AdminOrManagedVendorWrite`.
- `apps/vendors/admin.py`: Vendor list and edit configuration in Django admin.
- `apps/vendors/apps.py`: Django app registration metadata.

## Menu

- `apps/menu/models.py`: `MenuItem` is a vendor's sellable item. `MenuOptionGroup` represents a customization group; `MenuOption` represents a choice; `MenuAvailabilityWindow` represents a weekday/time range. `MenuOption.clean()` rejects duplicate option names across groups for one item when model validation runs. The models also define database constraints for selection bounds, duplicate options, and valid time ranges.
- `apps/menu/serializers.py`: Read serializers shape items/options/windows for API responses. Input serializers validate option names, selection limits, and time windows. `MenuItemSerializer.validate()` checks cross-group duplicate names and overlapping availability. `to_representation()` returns nested persisted options/windows. `create()` saves an item and its nested settings. `update()` updates an item and replaces a nested list only when that key is supplied. `_replace_option_groups()` and `_replace_availability_windows()` implement that replacement.
- `apps/menu/views.py`: `MenuItemViewSet` lists/retrieves menu items and allows create/update/delete subject to permissions. `perform_create()` and `perform_update()` ensure a vendor only changes items belonging to its managed vendor; admins can manage any vendor.
- `apps/menu/urls.py`: Registers `/api/menu/items/` list/detail routes.
- `apps/menu/admin.py`: Adds option groups, options, and availability windows to Django admin editing.
- `apps/menu/apps.py`: Django app registration metadata.

## Orders And Status Lifecycle

- `apps/orders/models.py`: `Order` stores the customer/vendor, delivery location, current status, and timestamps. `OrderItem` stores each ordered menu item, quantity, customization text, and price captured at order time. `OrderStatusHistory` stores each status transition, actor, note, and timestamp.
- `apps/orders/serializers.py`: `OrderItemWriteSerializer` validates submitted line items. `OrderItemSerializer` returns order lines. `OrderSerializer` returns an order plus `get_status_history()`. `CreateOrderSerializer.validate()` checks menu/vendor/availability/customizations and requires AI session/token together. `_validate_ai_confirmation()` verifies the signed token, user, session, and exact cart. `create()` saves the order/items/history transactionally and schedules a notification. `UpdateOrderStatusSerializer.update()` delegates status changes and maps invalid transitions into an API validation error.
- `apps/orders/views.py`: `OrderViewSet.get_queryset()` scopes orders to admins, the owning vendor, or the student who placed them. `get_serializer_class()` selects read/create/status serializers. `create_order()` creates an order; `update_status()` checks ownership, changes status, then invokes dispatch if ready.
- `apps/orders/services.py`: `transition_order()` locks the order, checks the allowed state transition, saves the status, writes history, and broadcasts the update after commit.
- `apps/orders/urls.py`: Maps order list/create, detail, and status-update routes.
- `apps/orders/admin.py`: Shows orders and their line items/status history; status history is read-only and current status is not directly edited in the admin form.
- `apps/orders/apps.py`: Django app registration metadata.

The vendor-facing status API currently allows accept, reject, preparing, and ready. Marking an order ready invokes the mock dispatch flow described below.

## Conversational Text Ordering

- `apps/conversational_ordering/schemas.py`: Pydantic structures `SlotConfidence`, `DraftLineItem`, and `ParsedOrder` validate model output and reject unexpected fields.
- `apps/conversational_ordering/groq_client.py`: `interpret_turn()` sends the transcript, live/frozen menu, current draft, and recent messages to Groq in JSON mode. It validates the response against `ParsedOrder`, retries one schema-invalid response, and raises `AIProviderError` for safe provider/configuration failures. This handles text only; it does not listen to a microphone or perform speech-to-text.
- `apps/conversational_ordering/menu_validation.py`: `normalize_text()` standardizes strings. `item_is_available()` checks item/vendor/time-window availability. `load_menu_catalog()` builds the structured menu sent to the model. `_match_score()` and `_candidate_items()` find possible menu matches. `validate_draft()` detects unknown/unavailable items, quantity/customization problems, missing details, and mixed vendors. `validate_order_submission()` repeats critical checks against current database rows immediately before order creation.
- `apps/conversational_ordering/sessions.py`: `cache_key()` creates the Redis key. `initial_session()` initializes a user's conversation state: messages, draft, question count, and submitted-order marker.
- `apps/conversational_ordering/policies.py`: `_load_policy_bundle()` lazily loads the trained C5 model. `choose_clarification_policy()` implements C1-C5 decisions; C5 uses the trained classifier if available and otherwise falls back to C3 rules. Safety-required repairs/questions are also enforced by the orchestration service.
- `apps/conversational_ordering/services.py`: Core conversation orchestration. `_signature_data()`, `confirmed_cart_signature()`, and `submission_cart_signature()` create comparable cart representations; `confirmation_token()` signs the confirmed cart for the current user/session. `_explicitly_mentions()` and `_preserve_untouched()` help preserve lines/location that a correction did not target. `_repair_question()` and `_clarification_question()` create user-facing prompts. `_signals()` calculates S1-S7 research features. `_draft_output()` formats the response. `_sample_agreement()` optionally repeats model parsing to estimate agreement. `parse_customer_turn()` combines model parsing, correction handling, menu validation, policy choice, question-budget/escalation behavior, and response/token creation.
- `apps/conversational_ordering/serializers.py`: Validates the AI endpoint's transcript (maximum 2,000 characters) and UUID session ID.
- `apps/conversational_ordering/views.py`: `ParseOrderView.post()` requires JWT authentication, loads/checks the Redis session owner, runs `parse_customer_turn()`, stores the updated session, and optionally writes a privacy-redacted research log when `AI_LOG_TURNS=True`. `_redact_contact_details()` removes common email/US phone patterns from logged text.
- `apps/conversational_ordering/urls.py`: Exposes `POST /api/ai/parse-order/`.
- `apps/conversational_ordering/models.py`: `AIConversationTurn` stores optional experiment/diagnostic turn logs, including transcript, draft, validation, signals, policy, latency, and token usage.
- `apps/conversational_ordering/admin.py`: Displays logs as read-only and disables admin-created/deleted log rows.
- `apps/conversational_ordering/apps.py`: Django app registration metadata.

Conversation path: frontend sends text plus a session UUID -> `ParseOrderView` checks Redis ownership -> `parse_customer_turn()` calls Groq -> schema and menu rules check the draft -> response says ASK/REPAIR/CONFIRM/ESCALATE -> frontend handles follow-up or confirmation -> `/api/orders/` verifies the signed cart and saves it.

## Dispatch And Notifications

- `apps/dispatch/models.py`: `RobotDispatch` records one dispatch per order, provider/status, and request/response JSON. It is a record/adapter scaffold, not physical robot control.
- `apps/dispatch/serializers.py`: `RobotDispatchSerializer` exposes dispatch fields.
- `apps/dispatch/views.py`: `RobotDispatchViewSet` is a read-only authenticated API for dispatch records.
- `apps/dispatch/urls.py`: Registers dispatch API routes.
- `apps/dispatch/services.py`: `trigger_dispatch_if_ready()` creates/updates a mock dispatch record when an order is READY, then transitions it to DISPATCHED.
- `apps/dispatch/admin.py`: Displays dispatch records in Django admin.
- `apps/dispatch/apps.py`: Django app registration metadata.
- `apps/notifications/services.py`: `broadcast_order_update()` publishes order ID/status/vendor/location/timestamp to the shared Channels group after order events.
- `apps/notifications/consumers.py`: `OrderUpdatesConsumer.connect()` joins the shared WebSocket group; `disconnect()` leaves it; `order_update()` sends event JSON to the socket.
- `apps/notifications/routing.py`: Maps `/ws/orders/` to the consumer.
- `apps/notifications/apps.py`: Django app registration metadata.

## Research And Management Commands

Run these through `python manage.py <command>` with the working directory set to `delivery-robot/backend`; they are for offline experiments, not normal customer requests.

- `export_menu_snapshot.py`: `Command.add_arguments()` reads `--output`; `handle()` saves a timestamped menu catalog and refuses to overwrite the chosen file.
- `split_dialogue_dataset.py`: `_read_jsonl()` loads annotated JSONL. `Command.add_arguments()` reads input/output/seed. `handle()` assigns whole `source_group`s to approximate category-stratified 60/20/20 train/validation/test splits, preventing group leakage and refusing to overwrite split files.
- `run_conversation_experiments.py`: `read_dialogues()` validates annotated conversations; `read_menu_snapshot()` loads a frozen catalog; `_canonical_items()` and `matches_gold()` compare draft/gold carts; `_write_jsonl()` writes feature rows. `Command.handle()` replays each dialogue under C1-C5 and writes metrics plus per-policy feature JSONL.
- `train_clarification_policy.py`: `read_rows()` loads labelled S1-S7 data; `clarification_rates()` measures missed/unnecessary questions; `Command.handle()` trains and calibrates a logistic-regression classifier, selects a threshold on validation data, and saves the C5 artifact.
- `evaluate_clarification_policies.py`: `expected_calibration_error()` measures probability calibration. `Command.handle()` compares C1-C5 decisions on held-out feature rows and reports question/error/calibration metrics.
- `export_ai_turn_logs.py`: `Command.handle()` exports opt-in database logs to JSONL; refuses to overwrite the destination.
- `purge_ai_turn_logs.py`: `Command.handle()` counts/removes logs older than a requested retention period; deletion requires `--confirm`.
- `management/__init__.py`, `management/commands/__init__.py`: Python package markers that let Django discover the management commands.

## Database Migrations

Migration files are versioned schema instructions generated/maintained by Django; they are not normal request handlers.

- `apps/accounts/migrations/0001_initial.py`: Creates the custom user table.
- `apps/vendors/migrations/0001_initial.py`: Creates vendor records.
- `apps/menu/migrations/0001_initial.py`: Creates the original menu-item table. `0002_menu_options_and_availability.py` adds max quantity, option groups/options, availability windows, and constraints.
- `apps/orders/migrations/0001_initial.py`: Creates orders and order items. `0002_order_status_history.py` adds status history and seeds a starting history row for pre-existing orders.
- `apps/dispatch/migrations/0001_initial.py`: Creates dispatch records.
- `apps/conversational_ordering/migrations/0001_initial.py`: Creates optional AI conversation-turn logs.
- Migration `__init__.py` files are package markers; `apps/notifications` currently has no database model migration.

Do not delete migrations to fix database problems. Apply new schema changes with `python manage.py migrate`; existing production data should be backed up before migrations.

## Important Boundaries Before Production

- Android voice input uses the device's configured speech-recognition service to create editable text. The backend has no audio-transcription endpoint.
- Physical robot control, store/POS integration, payment processing, and production deployment are not implemented. Dispatch currently records a mock robot acceptance.
- The Android and React frontends have not yet been verified with successful local builds against this backend.
- The current WebSocket consumer puts every connection in one shared group without checking user/vendor access. Dispatch reads also need role-based queryset scoping. Secure both before exposing live customer/order data.
- The current environment may still need `pip install -r requirements.txt`, `.env` values, migrations, Redis, and Groq configuration before the APIs run end to end.
