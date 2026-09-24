# Frontend Audit — Kutumba Hostel

> **Phase 2 deliverable.** Page-by-page audit of `apps/web` as it stood before the
> redesign, against the backend described in `PROJECT_ARCHITECTURE.md`.
> Findings marked *(by inspection)* come from reading code, not from reproducing them.

## Cross-cutting findings

| Area | Finding |
|---|---|
| Navigation | Flat top bar of text links; no icons, grouping or current-page semantics; wraps on phones. STAFF sees "Documents" but the API is warden-only. No notifications, notices or account entry points. |
| Auth | Sessions end after 15 minutes: nothing calls `/auth/refresh`. Query cache survives logout (shared-PC privacy risk). No server-side route guard, so pages flash "Loading…" before redirecting. |
| Data states | Queries ignore `isError`; failures render as "—" or as the empty state. Loading is plain text. No skeletons. |
| Lists | Every list endpoint is paginated (20 per page), but no page has paging controls, so only the first 20 rows are ever reachable. No filtering or sorting anywhere. |
| Forms | Controlled inputs with a copy-pasted class string; no field-level errors; server 422 field errors are discarded; no confirmation for consequential actions. |
| Components | Four primitives (`Card`, `Button`, `Badge`, `ErrorNote`). Page-local `Select`, `Stat`, `TriageRow` duplicate patterns other pages need. |
| Status colour | `Badge` tones cover about 10 values; PENDING, APPROVED, REJECTED, IN_PROGRESS, OVERDUE, PAID and others render grey. Two pages misuse unrelated tones to get a colour. |
| Visual | Generic: white cards on slate, one green accent, system font, no type scale, no depth or motion. |
| Responsive | Grids collapse, but the nav wraps and the fees table overflows on small screens. |
| Accessibility | Labels mostly present; focus styles inconsistent; colour-only meaning in places; no skip link; no `aria-current`. |

## Page-by-page

### `/login`
- **Purpose / role:** sign in; everyone.
- **APIs:** `POST /auth/login`.
- **Works:** sign-in, API error message, disabled button while busy.
- **Incomplete:** no password visibility toggle; after login always `/dashboard` (fine).
- **Visually weak:** centred white card on grey; nothing says "Kutumba" or "Pokhara".
- **Missing states:** none significant; rate-limit (429) message is passed through.

### `/dashboard`
- **Purpose / role:** landing page; both roles (same page).
- **APIs:** `GET /auth/me`, `GET /complaints`.
- **Works:** greeting; five latest complaints.
- **Incomplete:** student-only content shown to staff ("Your complaints" lists every complaint for staff; quick links to filing a complaint). No fees, room, notices, leave, menu or notifications — all available from the API.
- **Poor UX:** complaint links go to the generic list, not the complaint.
- **Missing states:** loading, error.

### `/complaints` (student)
- **APIs:** `GET /complaints`, `POST /complaints`.
- **Works:** filing (10–4000 chars, button disabled until 10), list with status/priority.
- **Incomplete:** no detail view (`GET /complaints/{id}` unused for students); only first 20; no status history.
- **Visually weak:** long raw text in a flat list; meta joined with "·".
- **Missing states:** loading, error; staff visiting see everyone's complaints under "Your complaints", and filing fails with 403.

### `/leave`
- **Role:** student (request) and staff (decide) on one page.
- **APIs:** `GET /auth/me`, `GET /leave`, `POST /leave`, `PATCH /leave/{id}`.
- **Works:** request form; approve/reject for staff.
- **Incomplete:** no decision note (API supports it); **the list does not say who requested the leave** (API returned only `student_id`); no status filter (API supports it); no paging.
- **Poor UX:** Approve/Reject shown to STAFF, who are refused by the API; the decide mutation has no error handling, so the click silently fails. No confirmation. Date range not validated in the UI.
- **Missing states:** loading, error, decide error.

### `/fees` (student)
- **APIs:** `GET /fees/balance`, `GET /fees/ledger`.
- **Works:** balance cards and ledger.
- **Incomplete:** invoices (list and line items) not shown although the API provides them; no due dates.
- **Visually weak / bug:** the ledger "Type" column renders the words *medium* and *positive* (tone keys reused as labels).
- **Missing states:** loading, error; staff visiting get a silent 422.

### `/mess`
- **Role:** both (students rate; staff read all feedback).
- **APIs:** `GET /mess/menu`, `GET /mess/feedback`, `POST /mess/feedback`.
- **Works:** today's menu, feedback form, feedback list with AI sentiment and issues.
- **Incomplete:** only today's menu (full week available); staff cannot edit the menu (API added); feedback form default date uses the UTC date while "today" uses local time.
- **Poor UX:** rating is a 1–5 `<select>`.
- **Missing states:** loading, error; duplicate-rating conflict shown only as raw message.

### `/assistant`
- **APIs:** `POST /assistant/ask`.
- **Works:** asks, shows answer and the tools that were checked; 503 handled with a clear message.
- **Incomplete:** document Q&A with citations (`POST /assistant/documents/ask`) has no UI; `conversation_id` not round-tripped (the backend does not persist conversations anyway); citations not rendered.
- **Visually weak:** stacked cards rather than a conversation.
- **Missing states:** rate limit (429) message.

### `/admin/complaints` (triage, staff)
- **APIs:** `GET /complaints`, `GET /complaints/{id}` per row, `PATCH /complaints/{id}`.
- **Works:** shows AI suggestion with model/prompt/confidence; saves overrides; marks overridden fields.
- **Incomplete:** labelled "Open complaints" but lists every status; no status filter; no paging (20 of 56 in the dev data); no status history.
- **Poor UX / performance:** an edit form for every complaint at once and one detail request per row (N+1).
- **Missing states:** per-row load error.

### `/admin/analytics` (staff)
- **APIs:** `GET /analytics/overview`, `POST /analytics/insights`.
- **Works:** four KPI tiles, category bars, AI briefing with a clear 503 message.
- **Visually weak:** bars are plain divs; no status breakdown, trend or mess detail although the payload includes them.
- **Missing states:** loading, error.

### `/admin/documents` (warden)
- **APIs:** `GET /documents`, `POST /documents` (raw `fetch`), `POST /documents/{id}/reindex`.
- **Works:** list; reindex; text/Markdown upload reaches the API.
- **Bugs:** PDF bodies are corrupted by the BFF (`req.text()`) *(by inspection)*; a successful upload shows "Upload failed." because `e.currentTarget` is read after `await` *(by inspection)*; status INDEXED is displayed as *resolved*.
- **Incomplete:** delete (API exists); processing error text not shown; reindex has no feedback.

### Shell / Nav (all pages)
- **APIs:** `GET /auth/me`, `POST /auth/logout`.
- **Works:** role-based link lists; sign out.
- **Incomplete:** no notifications bell, no account page, no mobile menu.

## Backend capabilities with no UI (to build in Phase 7)

| Capability | Role | Where it belongs |
|---|---|---|
| Students: directory, search, register, edit, deactivate, reactivate, reset password | Staff (lifecycle actions: warden) | `/admin/students` |
| Rooms: blocks, rooms, beds, occupancy, allocate, vacate | Staff (structure: warden) | `/admin/rooms` |
| Fees: invoices, invoice detail, manual invoice, payments, fee structures, monthly generation | Staff (structures, generation: warden) | `/admin/fees` |
| Fees: own invoices and line items | Student | `/fees` |
| Announcements: read; create/schedule/edit/delete | All; warden manages | `/notices` |
| Notifications: inbox, unread badge, mark read; delivery log and retry | All; log for warden | Top-bar bell + `/notifications` |
| Menu management | Staff | `/mess` (edit mode) |
| Reports (Excel/PDF) | Staff (residents, fees: warden) | `/admin/reports` |
| Change password | All | `/account` |
| Document Q&A with citations | All | `/assistant` |
| Document delete | Warden | `/admin/documents` |

## Components to build once and reuse

Buttons (variants, sizes, loading), text/select/textarea/checkbox fields with errors,
form section, data table with paging, filters/segmented controls, status pill with a
complete tone map, KPI tile, page header, panel, modal, side drawer, dropdown menu,
toasts, skeletons, empty state, error state, confirm dialog, file drop zone, charts.

---

## Outcome (Phases 4–9)

The old pages, `components/ui.tsx`, `nav.tsx`, `shell.tsx`, `lib/api.ts` and
`lib/clsx.ts` were replaced; nothing the old UI could do was dropped.

### Backend capabilities, now in the UI

| Capability | Where |
|---|---|
| Students: search, register, edit, check out or suspend, reactivate, reset password | `/admin/students` (drawer + modals) |
| Rooms: blocks, rooms, beds, allocate, vacate, 3D occupancy model | `/admin/rooms` |
| Fees (office): invoices with filters, detail, manual invoice, payments, fee schedule, bill a month | `/admin/fees` |
| Fees (resident): invoices with line items, account history | `/fees` |
| Notices: read; post, schedule, edit, delete | `/notices` (+ home) |
| Notifications: bell with unread count, inbox, mark read; email/SMS log with retry (warden) | top bar + `/notifications` |
| Menu management | `/mess` (edit per meal) |
| Reports, Excel and PDF | `/admin/reports` (personal-data reports warden-only) |
| Change password, reduce motion | `/account` |
| Document questions with citations | `/assistant` ("Rules and policies") |
| Document delete and re-index | `/admin/documents` |
| Paging and filters | every list |

### Defects from `PROJECT_ARCHITECTURE.md` §11, resolved

Sessions renew through `/auth/refresh` (single-flight across tabs); uploads keep
their bytes; upload success is reported as success; leave decisions take a note and
only the warden sees Approve/Reject; triage uses one paged, filtered request; homes
are split by role; badge tones come from one map per domain; the assistant renders
citations and uses the document endpoint; navigation follows `lib/permissions.ts`;
the query cache is cleared on sign-out and on session expiry; every query shows its
error with a retry; types are generated from OpenAPI; dates are hostel-local.

### Found and fixed during QA (Phases 8–9)

Driven by 23 end-to-end flows through the real UI (both roles) and screenshots of
every page at 1440, 1280 and 390 px, on an isolated stack with its own database.

- **Every 204 response became a 500 in the BFF** (pre-existing). The proxy built
  `new Response(emptyBuffer, { status: 204 })`, which throws. Broken: sign-out
  (the cookie-clearing headers were lost, so the access cookie stayed valid for up
  to 15 minutes on a shared PC), reset password (succeeded but showed an error),
  and deleting notices, documents, rooms, blocks, menu items and fees.
- **Staff notes were silently dropped** unless the status changed (the API files
  notes with status changes only). The note field now opens with a status change.
- **Success toasts could vanish.** Mutations awaited their refetch before running
  the page's own `onSuccess`; if fresh data re-keyed the form first, TanStack Query
  dropped the callback. Invalidation is no longer awaited.
- **Anything outside an open dialog is inert.** Toasts now render inside the open
  dialog (they were dimmed and unreachable behind drawers), and menus inside drawers
  render within them (the bed menu could not be clicked).
- Duplicate SVG gradient ids blanked the logo on phones; the unread badge hid the
  bell; tables forced a 640 px width on phones; the 3D model was cropped on narrow
  screens; the filter tabs overflowed at 390 px; the date picker icon was invisible;
  stacked dialogs shared one title id.
- Copy that promised more than the system guarantees was softened: the complaint page no longer says sorting "usually happens within
  minutes" or that staff "read every report", and the analytics chart now calls the status *Triaged* like everywhere else.
- Ratings no longer default to 4 stars (it skewed the averages); billing a month
  warns when the due date has already passed; payment lines in account history read
  "Payment by eSewa for INV-…" instead of an internal id.

### Still open (documented, not guessed)

- `leave_documents` has no API, so leave attachments are not offered.
- Assistant conversations are not stored (`conversation_id` is only echoed), and the
  write tools are never offered to the model; the page says it doesn't remember.
- Complaint `assigned_to_user_id` and `resolution_note` have no endpoint; invoice
  `VOID`, payment `REVERSED` and leave `CANCELLED` have no transition; no audit-log API.
- Billing a month after its due day produces invoices that are already overdue. The
  dialog warns when the due day is typed, but the default due day lives only in the
  API's settings, so the warning cannot cover an empty field.
- The Sparrow SMS adapter is untested against a live account (SMS is off by default).
