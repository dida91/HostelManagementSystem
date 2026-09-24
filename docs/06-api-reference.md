# API reference

The backend is a REST API under `/api/v1`. With the API running, interactive documentation with every field and example is at
<http://localhost:8000/docs> and the machine-readable schema at <http://localhost:8000/openapi.json>. **Those are the authority**;
this page is the overview: conventions, who may call what, and a one-line description of each of the
74 operations. The web app types itself from the same schema (`npm run gen:api`).

> This page was generated from the running application on 24 September 2026: the paths, parameters and access levels come from the
> code, and the descriptions were written by hand. If you add an endpoint, regenerate or extend the table.

## Conventions

**Signing in.** `POST /auth/login` returns `access_token` and `refresh_token` and also sets them as `httpOnly` cookies. Send the access token
either as `Authorization: Bearer <token>` or, as the web app does, as the `access_token` cookie. Access tokens last 15 minutes and refresh tokens 7 days.
The web app never calls the API directly from the browser: it goes through its own `/api/bff/*` proxy, which forwards the cookies.

**Who can call what** (the *Who* column):

| Value | Meaning |
|---|---|
| Anyone | No sign-in needed |
| Signed in | Any active account. Many of these are scoped by role inside the handler: residents get only their own rows |
| Resident | Signed in *and* a resident account (has a student record) |
| Staff+ | Staff, warden or administrator |
| Warden+ | Warden or administrator |

**Own data only.** A resident asking for another resident's complaint, invoice, profile or notification gets `404`, so its existence is not revealed. Asking for another
resident's fee statement (`student_id` on `/fees/balance` and `/fees/ledger`) gets `403`.

**Lists** take `limit` (default 20, maximum 100) and `offset`, and return `{"items": [...], "total": n, "limit": n, "offset": n}`.

**Errors** are `application/problem+json`: `type`, `title` (a short code), `status` and `detail`; validation errors add `errors.fields` with the location and message of each bad field. Internal details, SQL and provider messages are never returned.

| Status | `title` | When |
|---|---|---|
| 401 | `unauthenticated` | No valid session, or the account is inactive |
| 403 | `permission_denied` | The role may not do this |
| 404 | `not_found` | It does not exist, or it is not yours |
| 409 | `conflict` | It clashes with existing data: duplicate, occupied bed, block with rooms |
| 422 | `validation_failed` | The request is invalid (also used for rule violations such as a zero-value invoice) |
| 429 | `rate_limited` | Too many requests. Limits per minute: `auth` 10 (sign-in and password change), `ai` 20 (assistant and briefing) |
| 503 | `ai_temporarily_unavailable` | AI is not configured, the quota is used up, or the provider is failing. Everything else keeps working |

**Money** is in NPR and is returned as decimal strings with two places (for example `"13000.00"`); payments and invoices accept numbers or strings. Recording a payment requires an `Idempotency-Key` header. **Dates** are ISO 8601. Times are UTC with an offset; "today", due dates and scheduled jobs use the hostel's timezone (`Asia/Kathmandu`).

**Background work.** Some requests queue work after they commit (AI analysis of a complaint or meal comment, document indexing, sending email). The response does not wait for it.

## Operations

`*` marks a required parameter. Bodies are named by their schema in `/docs`.

### Health

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /health/live` | Anyone | The process is up. |  |  |
| `GET /health/ready` | Anyone | Reports the database, Redis and whether an AI key is configured. |  | AI is reported but does not affect `status`. |

### Auth

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `POST /auth/login` | Anyone | Sign in with email and password. Returns the tokens and sets the session cookies. | body: `LoginRequest` | Rate limit `auth`. Email is case-insensitive. |
| `POST /auth/refresh` | Anyone | Exchange the refresh token for a new pair. The old one stops working. |  | Reads the refresh cookie, or a JSON body `{"refresh_token": ...}`. Reusing a used token signs the user out everywhere. |
| `POST /auth/logout` | Anyone | Revoke the refresh token and clear both cookies. |  | Returns 204. |
| `POST /auth/change-password` | Signed in | Change your own password. Other sessions are signed out and this one gets fresh tokens. | body: `PasswordChange` | Rate limit `auth`. New password 10 to 128 characters and different from the current one. |
| `GET /auth/me` | Signed in | The signed-in user: id, email, name, role, and the resident id and code if a resident. |  |  |

### Residents (students)

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /students` | Staff+ | List or search residents. | query: `status`, `q`, `limit`, `offset` | `q` matches name, email or student code. Ordered by student code. |
| `POST /students` | Staff+ | Register a resident: creates the login and the record together, status Active. | body: `StudentCreate` | 409 if email, phone or student code is taken. Audited. |
| `GET /students/{student_id}` | Signed in | One resident with room and profile. |  | A resident may fetch only their own; anyone else's is 404. |
| `PATCH /students/{student_id}` | Staff+ | Edit profile fields. Only supplied fields change. | body: `StudentUpdate` | Audited. |
| `POST /students/{student_id}/deactivate` | Warden+ | Move a resident to `ALUMNI` or `SUSPENDED`: sign-in off, sessions revoked, bed optionally vacated. | body: `StudentDeactivate` | Body: `status`, `reason` (3 to 500), `vacate_bed`, `leaving_date`. `ALUMNI` always vacates. Audited. |
| `POST /students/{student_id}/reactivate` | Warden+ | Restore a resident to Active with sign-in on. Does not allocate a bed. |  | Audited. |
| `POST /students/{student_id}/reset-password` | Warden+ | Set a new password chosen by the warden; signs the resident out everywhere and notifies them. | body: `PasswordReset` | Body: `new_password`. The password is never written to the audit log. |

### Rooms, beds and allocations

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /rooms/blocks` | Staff+ | List blocks. |  |  |
| `POST /rooms/blocks` | Warden+ | Create a block. | body: `BlockCreate` | 409 if the name exists. |
| `PATCH /rooms/blocks/{block_id}` | Warden+ | Rename or edit a block. | body: `BlockUpdate` | Floors cannot drop below the highest existing room. |
| `DELETE /rooms/blocks/{block_id}` | Warden+ | Delete a block. |  | 409 if it still has rooms. Returns 204. |
| `PATCH /rooms/beds/{bed_id}` | Warden+ | Set a bed to `VACANT`, `RESERVED` or `OUT_OF_SERVICE`. | body: `BedUpdate` | A bed becomes occupied only through an allocation. 409 if someone holds it. |
| `GET /rooms` | Staff+ | List rooms with bed counts and occupancy. | query: `block_id`, `status` |  |
| `POST /rooms` | Warden+ | Create a room together with its beds (labelled A, B, C...). | body: `RoomCreate` | Bed count must fit the room type. 409 if the number exists in the block. |
| `POST /rooms/allocations` | Staff+ | Allocate a bed to a resident from a date. | body: `AllocationCreate` | 409 if the bed or resident is unavailable, the room is under maintenance or closed, or the resident is alumni or suspended. Notifies the resident. |
| `POST /rooms/allocations/{assignment_id}/vacate` | Staff+ | End an allocation as of today. The record is kept. |  |  |
| `GET /rooms/{room_id}` | Staff+ | One room with each bed and its current occupant. |  |  |
| `PATCH /rooms/{room_id}` | Warden+ | Edit a room: number, type, rent, status or number of beds. | body: `RoomUpdate` | Adds beds, or removes only never-used ones. 409 if residents still live in a room being closed. |
| `DELETE /rooms/{room_id}` | Warden+ | Delete a room that has never been lived in. |  | 409 otherwise. Returns 204. |

### Complaints

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `POST /complaints` | Resident | File a complaint (10 to 4000 characters). | body: `ComplaintCreate` | Saved at once; AI analysis is queued after the request commits. Non-resident accounts get 403. |
| `GET /complaints` | Signed in | List complaints. Residents get their own; staff get all. | query: `status`, `limit`, `offset` | `status` may be repeated to match several statuses. |
| `GET /complaints/{complaint_id}` | Signed in | One complaint with the AI analysis, if any. |  | Another resident's complaint is 404. |
| `PATCH /complaints/{complaint_id}` | Staff+ | Override triage fields (category, priority, department, location, summary) or the status. | body: `ComplaintOverride` | Only supplied fields change and are recorded as overrides. `note` is saved with a status change. Audited. A status change notifies the resident. |

### Leave

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `POST /leave` | Resident | Request leave. | body: `LeaveCreate` | `to_date` may not precede `from_date`; `reason` at least 5 characters. Notifies the warden. |
| `GET /leave` | Signed in | List leave requests. Residents get their own; staff get all, with the resident's name and code. | query: `status`, `limit`, `offset` | Newest first by start date. |
| `PATCH /leave/{leave_id}` | Warden+ | Decide a pending request: `APPROVED` or `REJECTED`, with an optional note. | body: `LeaveDecision` | 422 if already decided. Notifies the resident. |

### Fees, invoices and payments

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /fees/balance` | Signed in | Outstanding balance, charged and paid, summed from the ledger. | query: `student_id` | Residents get their own. Staff must pass `student_id`. A resident passing someone else's id gets 403. |
| `GET /fees/ledger` | Signed in | The ledger lines (charges and payments), newest first. | query: `student_id` | Same `student_id` rule as `balance`. |
| `GET /fees/structures` | Staff+ | The fee schedule. |  |  |
| `POST /fees/structures` | Warden+ | Add a fee: name, amount, `MONTHLY` or `ONE_TIME`, effective dates. | body: `FeeStructureCreate` | Audited. |
| `PATCH /fees/structures/{structure_id}` | Warden+ | Edit a fee. | body: `FeeStructureUpdate` | Audited. Issued invoices keep their amounts. |
| `DELETE /fees/structures/{structure_id}` | Warden+ | Delete a fee. |  | Audited. Returns 204. |
| `GET /fees/invoices` | Signed in | List invoices with totals. Residents get their own. | query: `student_id`, `status`, `billing_period`, `limit`, `offset` | `billing_period` is `YYYY-MM`. |
| `POST /fees/invoices` | Staff+ | Issue a one-off invoice with line items; posts the matching ledger debit and notifies the resident. | body: `InvoiceCreate` | Total must be above zero (422). Numbers look like `INV-202609-00009`. |
| `POST /fees/invoices/generate` | Warden+ | Bill a month: room rent plus monthly fees for every resident holding a bed. | body: `InvoiceGenerate` | Body: optional `period` (`YYYY-MM`, default this month) and `due_day` (1 to 28). Safe to repeat: residents already billed are skipped. Audited. Returns counts and the new invoices. |
| `GET /fees/invoices/{invoice_id}` | Signed in | One invoice with line items, paid and outstanding. |  | Another resident's invoice is 404. |
| `POST /fees/payments` | Staff+ | Record a payment and post the matching ledger credit; settles the invoice when fully paid. | header: `Idempotency-Key`; body: `PaymentCreate` | **`Idempotency-Key` header required**: a repeat with the same key returns the first payment. The invoice must belong to the same resident and not be void. Notifies the resident. |

### Mess

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /mess/menu` | Anyone | The weekly menu. | query: `day_of_week` | **No sign-in needed.** `day_of_week`: 0 is Sunday. |
| `PUT /mess/menu/{day_of_week}/{meal_type}` | Staff+ | Set or replace what is served for one meal on one day. | body: `MenuUpsert` | `meal_type`: `BREAKFAST`, `LUNCH`, `SNACKS`, `DINNER`. |
| `DELETE /mess/menu/{day_of_week}/{meal_type}` | Staff+ | Stop serving a meal on that day. |  | 404 if nothing is set. Returns 204. |
| `POST /mess/feedback` | Resident | Rate a meal (1 to 5) with an optional comment. | body: `MessFeedbackCreate` | 409 if already rated that meal on that date. A comment queues AI analysis. |
| `GET /mess/feedback` | Signed in | List ratings. Residents get their own; staff get all with the AI mood and issues. | query: `limit`, `offset` |  |

### Notices (announcements)

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /announcements` | Signed in | Notices visible to your role, newest first (up to 50). | query: `include_expired` | Residents never see staff-only or not-yet-published notices. Staff with `include_expired=true` also see scheduled and expired ones. |
| `POST /announcements` | Warden+ | Post a notice: title, body, audience (`ALL`, `STUDENTS`, `STAFF`), optional publish and expiry times. | body: `AnnouncementCreate` | Notifies the audience now, or at the publish time. |
| `PATCH /announcements/{announcement_id}` | Warden+ | Edit a notice. | body: `AnnouncementUpdate` | Audited. |
| `DELETE /announcements/{announcement_id}` | Warden+ | Delete a notice. |  | Audited. Returns 204. |

### Documents

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `POST /documents` | Warden+ | Upload a PDF, text or Markdown document (multipart: `file`, `title`, `doc_type`, `language`). | body: multipart form | Up to 20 MB, checked by content. Indexing is queued after commit. |
| `GET /documents` | Warden+ | List documents with status and chunk counts. | query: `limit`, `offset` |  |
| `POST /documents/{document_id}/reindex` | Warden+ | Queue parsing and embedding again. |  |  |
| `DELETE /documents/{document_id}` | Warden+ | Delete a document, its chunks, embeddings and stored file. |  | Returns 204. |

### Assistant

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `POST /assistant/ask` | Signed in | Ask the tool-calling assistant a question about your own records or the hostel. | body: `AssistantAsk` | Rate limit `ai`. Body: `message` (1 to 2000). 503 if AI is unavailable. The conversation is not stored. |
| `POST /assistant/documents/ask` | Signed in | Ask a question answered only from the hostel documents, with citations. | body: `RagAsk` | Rate limit `ai`. Returns `grounded: false` if the documents do not cover it. 503 if AI is unavailable. |

### Analytics

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /analytics/overview` | Staff+ | Occupancy, complaints, fees and mess figures in one call. | query: `days` | `days` 1 to 365, default 30. |
| `GET /analytics/occupancy` | Staff+ | Beds total, occupied, vacant and rate. |  |  |
| `GET /analytics/complaints` | Staff+ | Complaints in the window: by category and status, open count, change from the previous period, median hours to resolve. | query: `days` | `days` 1 to 365. |
| `GET /analytics/fees` | Staff+ | Charged, collected and outstanding across all residents, and the collection rate. |  | Outstanding is charged minus collected in total, so a resident in credit offsets others' arrears here. |
| `POST /analytics/insights` | Staff+ | A short AI-written briefing of the overview figures. | body: `InsightRequest` | Rate limit `ai`. Body: `days`, optional `question`. 503 if AI is unavailable. |

### Notifications

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /notifications` | Signed in | Your notifications and your unread count. | query: `unread_only`, `limit`, `offset` |  |
| `POST /notifications/read-all` | Signed in | Mark all your notifications read. |  |  |
| `POST /notifications/{notification_id}/read` | Signed in | Mark one of your notifications read. |  | Someone else's is 404. |
| `GET /notifications/deliveries` | Warden+ | The email and SMS log: status, attempts and errors. | query: `status`, `limit`, `offset` | `status`: `PENDING`, `SENDING`, `SENT`, `FAILED`. |
| `POST /notifications/deliveries/retry-failed` | Warden+ | Requeue every failed delivery. |  | Audited. |

### Reports

| Operation | Who | What it does | Parameters | Notes |
|---|---|---|---|---|
| `GET /reports/students` | Warden+ | Resident register as Excel or PDF. | query: `format`, `status` | `format`: `xlsx` (default) or `pdf`. Personal data; the download is never cached. Audited. |
| `GET /reports/occupancy` | Staff+ | Every room with beds, rent and residents. | query: `format` | `format`: `xlsx` (default) or `pdf`. Audited. |
| `GET /reports/fees` | Warden+ | Balances for every resident, plus one month's invoices (`period`) or all unpaid ones. | query: `format`, `period` | Personal data. Audited. |
| `GET /reports/complaints` | Staff+ | Complaints by category and in detail for a date range. Who filed each is left out. | query: `format`, `date_from`, `date_to` | Dates default to the last 30 days and may span at most a year. Audited. |
| `GET /reports/leave` | Staff+ | Leave register for a date range. | query: `format`, `date_from`, `date_to` | Dates default to the last 30 days and may span at most a year. Audited. |

## Values used across the API

Stored as native PostgreSQL enums, so the database itself rejects any other value.

| What | Values |
|---|---|
| Roles (`UserRole`) | `SUPER_ADMIN`, `WARDEN`, `STAFF`, `STUDENT` |
| Resident status (`StudentStatus`) | `PROSPECTIVE`, `ACTIVE`, `ON_LEAVE`, `ALUMNI`, `SUSPENDED` |
| Room type (`RoomType`) | `SINGLE`, `DOUBLE`, `TRIPLE`, `DORMITORY` |
| Room status (`RoomStatus`) | `AVAILABLE`, `FULL`, `MAINTENANCE`, `CLOSED` |
| Bed status (`BedStatus`) | `VACANT`, `OCCUPIED`, `RESERVED`, `OUT_OF_SERVICE` |
| Complaint category (`ComplaintCategory`) | `WATER`, `ELECTRICITY`, `INTERNET`, `CLEANLINESS`, `FOOD`, `MAINTENANCE`, `SECURITY`, `NOISE`, `HARASSMENT`, `STAFF_BEHAVIOUR`, `OTHER` |
| Complaint priority (`ComplaintPriority`) | `LOW`, `MEDIUM`, `HIGH`, `URGENT` |
| Complaint status (`ComplaintStatus`) | `SUBMITTED`, `TRIAGED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, `REJECTED` |
| Department (`Department`) | `MAINTENANCE`, `HOUSEKEEPING`, `MESS`, `SECURITY`, `IT`, `ADMINISTRATION`, `WARDEN_OFFICE` |
| Leave type (`LeaveType`) | `HOME_VISIT`, `MEDICAL`, `ACADEMIC`, `EMERGENCY`, `OTHER` |
| Leave status (`LeaveStatus`) | `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`, `COMPLETED` |
| Invoice status (`InvoiceStatus`) | `DRAFT`, `ISSUED`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`, `VOID` |
| Payment method (`PaymentMethod`) | `CASH`, `BANK_TRANSFER`, `ESEWA`, `KHALTI`, `CHEQUE` |
| Meal (`MealType`) | `BREAKFAST`, `LUNCH`, `SNACKS`, `DINNER` |
| Document kind (`DocumentType`) | `HOSTEL_RULES`, `FEE_POLICY`, `LEAVE_POLICY`, `MESS_POLICY`, `NOTICE`, `FAQ`, `OTHER` |
| Document status (`DocumentStatus`) | `UPLOADED`, `PROCESSING`, `INDEXED`, `FAILED`, `ARCHIVED` |
| Notification category (`NotificationCategory`) | `ANNOUNCEMENT`, `LEAVE_REQUESTED`, `LEAVE_DECIDED`, `COMPLAINT_UPDATED`, `INVOICE_ISSUED`, `FEE_REMINDER`, `FEE_OVERDUE`, `PAYMENT_RECEIVED`, `ROOM_ALLOCATED`, `ACCOUNT_SECURITY` |
| Delivery status (`DeliveryStatus`) | `PENDING`, `SENDING`, `SENT`, `FAILED` |
