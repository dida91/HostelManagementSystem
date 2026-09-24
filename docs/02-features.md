# Features: everything the system can do

This is the reference for the system's functions, module by module: what each one does,
who may use it, the rules it enforces, and what it triggers (notifications, background
work, AI). For step-by-step instructions see the [user guide](04-user-guide.md).

Contents: [Who can do what](#who-can-do-what) ·
[1. Accounts and security](#1-accounts-and-security) · [2. Residents](#2-residents) ·
[3. Rooms and beds](#3-rooms-and-beds) · [4. Complaints](#4-complaints) ·
[5. Leave](#5-leave) · [6. Fees and billing](#6-fees-and-billing) · [7. Mess](#7-mess) ·
[8. Notices](#8-notices) · [9. Notifications](#9-notifications) ·
[10. Reports](#10-reports) · [11. Analytics](#11-analytics) ·
[12. Assistant and documents](#12-assistant-and-documents) ·
[13. Scheduled jobs](#13-scheduled-jobs) · [14. The interface](#14-the-interface) ·
[15. Audit and history](#15-audit-and-history)

---

## Who can do what

There are four roles. **Staff** can do everything a resident-facing office needs day to
day. **Warden** can do everything staff can, plus the sensitive actions. **Administrator**
(`SUPER_ADMIN`) has the same permissions as the warden today.

| Function | Resident | Staff | Warden / Administrator |
|---|:-:|:-:|:-:|
| Sign in, change own password, read notifications, use the assistant | yes | yes | yes |
| Read notices (filtered to their audience) | yes | yes | yes |
| File and track **own** complaints | yes | | |
| See all complaints, triage and override them | | yes | yes |
| Request leave and see **own** leave | yes | | |
| See all leave requests | | yes | yes |
| **Approve or reject** leave | | | yes |
| See **own** fees, invoices and ledger | yes | | |
| See any resident's fees; issue invoices; record payments | | yes | yes |
| View the fee schedule | | yes | yes |
| Create, edit, delete fee-schedule items; **bill a month** | | | yes |
| View rooms and beds; allocate and vacate beds | | yes | yes |
| Create, edit, delete blocks and rooms; set bed status | | | yes |
| List, search, register and edit residents | | yes | yes |
| **Check out or suspend, reactivate, reset password** for a resident | | | yes |
| View the weekly menu (no sign-in needed for the menu API) | yes | yes | yes |
| Rate meals | yes | | |
| Edit the menu; see all meal feedback and its insights | | yes | yes |
| Post, schedule, edit, delete notices | | | yes |
| Upload, re-index, delete documents for the assistant | | | yes |
| Analytics page and AI briefing | | yes | yes |
| Reports: occupancy, complaints, leave | | yes | yes |
| Reports: **residents, fees** (personal data) | | | yes |
| Email/SMS delivery log and retry | | | yes |

Two rules sit underneath the table. A resident can only ever reach their own records: if they ask for another resident's complaint, invoice or profile the answer is "not found", so they cannot even learn that it exists, and asking for another resident's fee statement is refused
outright. And the web interface hides what a role cannot use, but that is a courtesy: the
server checks every request itself.

---

## 1. Accounts and security

- **Sign in** with email and password. Wrong email and wrong password are
  indistinguishable, and sign-in is limited to 10 attempts a minute per client.
- **Sessions.** Signing in gives a short-lived access token (15 minutes) and a refresh
  token (7 days), both kept in secure cookies that page scripts cannot read. The web app
  renews the session on its own, including across several open tabs. If it cannot,
  you are sent to the sign-in page with a message.
- **Sign out** ends the session and clears the cookies.
- **Passwords** must be at least 10 characters and are stored only as Argon2 hashes.
  Changing your password (you must give the current one, and the new one must differ)
  signs you out everywhere else and sends you a notification. A warden reset does the same
  and tells the resident.
- **Deactivating a resident** blocks sign-in immediately and ends every open session.
- **Who can create accounts.** Staff and wardens register *residents* in the app. There
  is no screen for creating staff or warden accounts; see
  [Adding a staff or warden account](03-getting-started.md#adding-a-staff-or-warden-account).
- **Account page** (`/account`): read-only profile, change password, and a switch that
  turns off animation and the 3D scenes on this device.

---

## 2. Residents

Screen: **Students** (staff and warden). API name: students.

- **Directory.** Search by name, email or student code; filter by status (Active,
  Prospective, On leave, Alumni, Suspended); paged. Each row shows code, room, college
  and status.
- **Register a resident** (staff and warden). Required: full name, student code
  (unique), email (unique, used to sign in) and a first password (at least 10
  characters; a button generates one). Optional: mobile, college, program, guardian and
  guardian's phone, admission date. Registering creates the login and the record
  together. The resident is created as *Active*; a bed is allocated separately.
- **Profile** (drawer). Fees outstanding, current room, contact details, guardian and
  emergency contact, home address.
- **Edit profile** (staff and warden): name, email, mobile, college, program, guardian,
  relation, guardian's phone, emergency contact, admission date, date of birth and home
  address. Only changed fields are saved.
- **Check out or suspend** (warden). Choose *Alumni* or *Suspended*, give a reason
  (recorded), and optionally a leaving date. Sign-in is turned off at once and all sessions
  end. An alumnus's bed is always freed; for a suspension you choose. Fees, complaints
  and leave records are kept.
- **Reactivate** (warden). Restores an alumnus or suspended resident to Active with sign-in
  on again. It does not allocate a bed.
- **Reset password** (warden). Sets a new password (a generator is offered), signs the resident out everywhere and notifies them.

---

## 3. Rooms and beds

Screen: **Rooms** (staff and warden).

- **3D model and room grid.** Blocks are drawn as stacks of rooms coloured by how full they
  are: empty, partly filled, full, maintenance, closed. Below it, each block lists its rooms
  with a bed-by-bed fill bar. Select a room in either view. On phones the 3D model is
  view-only so the page still scrolls, and the grid is the main control. With WebGL
  unavailable the grid alone is shown.
- **Blocks** (warden): add, rename, change description or number of floors, delete. A block
  with rooms cannot be deleted, and floors cannot be reduced below the highest room.
- **Rooms** (warden): add with block, floor, room number, type, number of beds and monthly
  rent (NPR). Room types and their bed counts: single 1, double 2, triple 3, dormitory 4 to
  12. Beds are created with the room and labelled A, B, C... Room numbers are unique within a
  block. Status can be available, full, maintenance or closed. Changing the number of beds
  adds beds, or removes only beds that were never used. A room that has ever housed someone
  cannot be deleted, only closed, so residency history is never lost.
- **Bed status** (warden): mark available, reserve, or take out of service.
- **Allocate a bed** (staff and warden): choose a resident (search-as-you-type) and a start
  date. The system refuses if the bed is occupied or out of service, if the room is under
  maintenance or closed, if the resident already has an active bed, or if the resident is an
  alumnus or suspended. The database enforces the one-bed and one-resident rules even when
  two people click at the same moment. The resident is notified.
- **Vacate a bed** (staff and warden): ends the allocation as of today. The record is kept.

---

## 4. Complaints

Screens: **Complaints** (resident) and **Complaints** triage (staff and warden).

**Resident**
- Writes a complaint in their own words, English or Nepali (10 to 4000 characters), and sends
  it. It is saved immediately, even if the AI is unavailable.
- Sees their own complaints with status (Submitted, Triaged, In progress, Resolved, Closed,
  Rejected), and is notified whenever staff change the status.

**AI triage** (background, needs a Gemini key and the worker)
- For each new complaint the AI proposes: **category** (water, electricity, internet,
  cleanliness, food, maintenance, security, noise, harassment, staff behaviour, other),
  **priority** (low, medium, high, urgent), **department** (maintenance, housekeeping, mess,
  security, IT, administration, warden's office), a location if the resident stated one, a
  one-sentence English summary, the tone, and a confidence value.
- Its instructions: base everything only on what was written; never guess a location; treat
  safety, security, harassment or a health risk as urgent; never put the resident's name in
  the summary.
- The proposal fills the complaint's fields only where staff have not already set them, and
  moves a new complaint from *Submitted* to *Triaged*. The model's own answer is stored
  unchanged so its agreement with staff decisions can be measured later. If the AI fails,
  the failure is recorded and visible; the complaint is still there for manual triage.

**Staff and warden**
- **Triage list**: tabs for Open (with a count), Resolved, Rejected and All. Columns:
  priority, report, category, sent to, filed, status. Paged.
- **Complaint drawer**: the complaint, the AI suggestion (with model and prompt version, marked
  advisory), and the triage form for status, priority, category and department, plus an
  internal staff note. Only changed fields are sent. The note is saved with a status change
  and no resident-facing screen or API returns it. (Nothing in the interface shows the history
  of a complaint's status changes and notes yet; they are stored in the database.)
- **Overrides always win** and are recorded (which fields staff set, by whom, when).
- Changing the status notifies the resident.

---

## 5. Leave

Screen: **Leave**.

**Resident** requests leave with: type (home visit, medical, academic, emergency, other),
from and to dates (the end cannot be before the start), where they will be (optional), the
reason (at least 5 characters) and a tick-box "My guardian knows and agrees". Their requests are listed with status and the warden's note. Statuses: Pending, Approved, Rejected,
Completed (Cancelled exists but has no screen).

**Office** sees every request with the resident's name and code, filtered by Waiting, Approved,
Rejected, Completed or All. A request opens in a drawer with the details.

**Warden** approves or rejects a pending request, with an optional note to the resident.
A request can be decided only once. Staff (non-warden) can see requests but not decide them.

**Automatic.** A new request notifies the warden (and administrators), the people who can decide it.
A decision notifies the resident (and by SMS if that channel is ever enabled). Approved leave becomes *Completed* by
itself after its last day, so "who is away now" stays accurate.

---

## 6. Fees and billing

Screens: **Fees** (resident, and a different one for staff and warden).

**How money is recorded.** Every charge and payment becomes a line in the resident's
*ledger*: a charge is a debit, a payment a credit. Their balance is the sum of their ledger,
calculated by the database each time. There is no balance field anywhere that a person or
the AI could type into. Lines are only ever added.

**Resident view.** Three figures (outstanding, charged to date, paid to date), their invoices with line items, and their account history (each charge and payment, newest first). Payment lines
read like "Payment by eSewa for INV-202609-00001".

**Fee schedule** (view: staff and warden; change: warden). Each fee has a name, an
amount, whether it is *monthly* or *one-time*, an effective-from date and an optional end date.
Room rent is not a fee-schedule item: it comes from each room's monthly rate.

**Bill a month** (warden; also automatic on the 1st at 06:00). For a chosen month, the system
invoices every resident who holds a bed that started on or before the month's last day:
their room's monthly rent plus every monthly fee in effect that month. Rules:
- A resident is billed once per month. Running it again skips people already billed, even if
  two people run it at the same second.
- Residents with nothing to charge are skipped and counted.
- The due date is the 10th by default (configurable, 1st to 28th) or a day you choose. If
  the due date is already in the past, the dialog warns you that the invoices would be overdue
  immediately.
- Mid-month arrivals are billed the full month; issue a manual invoice for a part month.
- The result shows how many invoices were issued, skipped as already billed, and skipped for
  having nothing to charge.

**Issue an invoice** (staff and warden). Choose a resident, the period, a due date, and one or
more line items (description, quantity, unit amount) with an optional note. The total must be
above zero. Invoice numbers look like `INV-202609-00009`, and are never reused, even under
simultaneous requests.

**Record a payment** (staff and warden). Choose a resident, optionally the invoice it pays,
the amount, the method (cash, bank transfer, eSewa, Khalti, cheque), a reference and the time
received. A payment must belong to the same resident as the invoice, and cannot go against a
voided invoice. Part payments are supported: the invoice shows *Partially paid* until it is
settled, and stays *Overdue* if it was already late. Each payment carries an idempotency
key, so a double click or a retry on a poor connection cannot record it twice. The resident is
notified.

**Statuses.** Invoices are Issued, Partially paid, Paid, Overdue, or Void (Void has no screen
yet). Overdue marking and reminders run automatically (see [scheduled jobs](#13-scheduled-jobs)).

**Office view.** Outstanding, collected and collection-rate figures; the invoice list with filters
by status and billing month; the fee schedule tab; and an invoice drawer that shows the line
items, what has been paid and what remains, and a *Record payment* button.

---

## 7. Mess

Screen: **Mess**.

- **Weekly menu.** Breakfast, lunch, snacks and dinner for each day of the week, each with what
  is served and a serving time. A day selector jumps to any day; *Today* is highlighted.
- **Edit the menu** (staff and warden): edit or add any meal for any day; remove a meal
  ("Stop serving").
- **Rate a meal** (resident). Choose the date (the picker stops at today), the meal, a rating from
  1 to 5 and an optional comment in English or Nepali. There is no default rating, so averages are
  not skewed. One rating per resident per meal per day; a second one for the same meal is refused.
- **AI feedback analysis** (background). Each comment gets a mood (positive, neutral,
  negative, mixed), topics and specific issues, stored *alongside* the original, which is
  never changed.
- **Staff view.** All ratings, newest first, with the AI's mood and issues; the average rating
  over 30 days and average by meal.

---

## 8. Notices

Screen: **Notices**.

- **Read.** Residents see notices for *Everyone* or *Residents*; staff also see *Staff* notices.
  Only notices whose publish time has arrived, and that have not expired, are shown.
- **Post** (warden): title, message, audience (everyone, residents, staff), optional publish
  time (schedule for later) and optional expiry. Posting notifies the audience; a scheduled
  notice notifies at its publish time, once per person.
- **Edit and delete** (warden). A tick-box shows scheduled and expired notices too.

---

## 9. Notifications

Screen: the bell in the top bar, and **Notifications**.

- **In the app (always on).** Every event below creates a notification with a title, text and a link.
  The bell shows the unread count. Filter All or Unread; mark one or all as read.
- **By email (optional).** If an SMTP server is configured, each notification is also emailed to
  the person's account address, with a link to the portal.
- **By SMS (off).** The Sparrow SMS adapter exists but is disabled and untested against a live
  account. When enabled it would send only leave decisions, fee reminders and overdue notices, only to
  valid Nepali mobile numbers.
- **Delivery log** (warden). Every email or SMS with its status (pending, sending, sent,
  failed), number of tries and error. Failed deliveries can be retried. Delivery is retried
  automatically with growing pauses (1, 5 then 30 minutes) up to four attempts.

| Event | Who is notified |
|---|---|
| A resident requests leave | The warden (and administrators) |
| Leave approved or rejected | The resident |
| Complaint status changed | The resident |
| Invoice issued (including monthly billing) | The resident |
| Fee due reminder; invoice overdue | The resident |
| Payment recorded | The resident |
| Bed allocated | The resident |
| Notice posted or reaching its publish time | The notice's audience |
| Password changed by the resident, or reset by the warden | The resident |

Only active accounts are notified.

---

## 10. Reports

Screen: **Reports** (staff and warden). Each report downloads as **Excel** or **PDF**, and every
export is recorded in the audit log.

| Report | Contents | Who |
|---|---|---|
| Resident register | Contact, college, room and guardian details; filter by status | Warden |
| Occupancy | Every room with its beds, rent and current residents | Staff, warden |
| Fees | Every resident's balance, plus one month's invoices or all unpaid ones | Warden |
| Complaints | By category and in detail, for a date range. **Who filed each complaint is left out on purpose**, so a report about harassment or a staff member does not travel with a name attached | Staff, warden |
| Leave register | Who was away, when, and the decision, for a date range | Staff, warden |

Excel cells that could be read as formulas are neutralised. PDFs shape Nepali (Devanagari) text
correctly when the server has a Devanagari font installed; if it does not, the PDF says so and the
Excel file has the exact text.

---

## 11. Analytics

Screen: **Analytics** (staff and warden), over 30 days, 90 days or a year.

- **Tiles:** beds occupied (percentage and counts), complaints filed and how many are still open,
  median time to resolve, and mess rating.
- **Charts:** complaints by category; where complaints stand by status; beds occupied and fees
  collected; mess rating by meal.
- **Figures.** Every number is computed by the database.
- **AI briefing** (optional, needs a key): a three-to-five-sentence written summary of the figures for
  the warden. It is given the finished numbers and told to use them exactly and to say so when the
  data cannot explain a trend. It never produces a number of its own.

The home screens also show headline figures: for residents, fees outstanding, today's menu, notices,
their complaints and leave; for the office, occupancy, open complaints, fees outstanding, mess rating,
"needs attention" (open complaints, most urgent first), leave waiting, beds by block and notices.

---

## 12. Assistant and documents

Screen: **Assistant** (everyone) and **Documents** (warden).

**Assistant.** Two modes, chosen by a switch. It answers one question at a time and does not
remember earlier questions, so include the details each time.

1. **Your records.** The assistant can call a fixed set of read-only tools to answer questions about the
   signed-in person's own data: profile, room assignment, fee balance, leave requests, complaint
   status, the mess menu, active notices, and the hostel documents. Staff can also ask for the occupancy
   summary. Rules it must follow: for anything about a person's data it must call the tool, never state
   a figure from memory; if a tool fails it says it could not retrieve it rather than estimating;
   it cannot ask for anyone else's data, because the tools have no "whose data?" input. The personal
   tools are for resident accounts; staff accounts get an error from them.
2. **Rules and policies.** The question is matched against the uploaded documents (meaning-based
   and keyword search combined), and the answer is written **only** from the passages found, with citations
   to the document and page. If the documents do not cover it, it says so ("not grounded") instead of
   guessing. It answers in the language of the question (English or Nepali).

Both modes are limited to 20 questions a minute per person. Create-complaint and create-leave tools
exist in the code but are never offered to the model.

**Documents** (warden). Upload PDF, plain text or Markdown files (up to 20 MB) with a title, kind
(hostel rules, fee policy, leave policy, mess policy, notice, FAQ, other) and language. Files are
recognised by their content, not their name. In the background each document is read (pages with too
little text, such as scans, are read by the AI), split along headings and clauses so a numbered rule is
not cut in half, and indexed for search. Status: Uploaded, Processing, Indexed, Failed. Failed or changed
documents can be re-indexed; a document can be deleted (its chunks, embeddings and stored file go too).
Until at least one document is indexed the assistant cannot answer policy questions.

---

## 13. Scheduled jobs

Run by the worker; all times are hostel time (Asia/Kathmandu). Each job is safe to run twice.

| Job | When |
|---|---|
| Send queued email and SMS, retrying failures | Every 30 seconds |
| Notify notices whose publish time has arrived | Every 5 minutes |
| Generate the month's invoices (room rent plus monthly fees) | 1st of the month, 06:00 |
| Mark unpaid invoices past their due date as overdue, and notify once | Daily, 00:30 |
| Send fee-due reminders (3 days before the due date by default) | Daily, 09:00 |
| Complete approved leave whose last day has passed | Daily, 00:45 |
| Remove expired sign-in tokens | Daily, 03:15 |

On demand, also in the background: AI analysis of a new complaint, AI analysis of a meal rating with a
comment, indexing a document, and delivering notifications.

Automatic monthly billing can be turned off (`AUTO_GENERATE_MONTHLY_INVOICES=false`) if the warden
prefers to press *Bill a month* by hand.

---

## 14. The interface

- **Role-aware navigation.** Residents see Home, Complaints, Leave, Fees, Mess, Notices, Assistant. The
  office sees grouped sections: Overview, Residents, Daily life, Money, Knowledge, with only the pages
  its role may use.
- **Go to...** (`Ctrl`+`K`, or `⌘`+`K` on a Mac) opens a search box that jumps to any page.
- **Works on phones.** Down to a 390-pixel screen: the sidebar becomes a menu, tables show their key
  columns and keep the rest in the detail panel, and forms stack.
- **Loading, empty and error states.** Every list and page shows a skeleton while loading, a helpful
  message when empty, and an error with a Retry button when the server cannot be reached. A page a role
  may not open says so and links home.
- **Two 3D scenes, used sparingly.** The mountain skyline on the sign-in page and home banners, and the
  block model on Rooms. They load only on those pages, pause when off screen or when the browser tab is in
  the background, and stand still when the operating system or the Account switch asks for reduced motion.
  Without WebGL, a drawing or the plain room grid takes their place.
- **Language.** The interface is in English. Nepali text is supported in everything residents write and in
  PDFs.
- **Accessibility basics.** Keyboard operation of menus, dialogs and tables; visible focus; a
  skip-to-content link; dialogs that trap focus and close with `Esc`; chart colours checked for
  colour-blind safety and contrast.

---

## 15. Audit and history

- **Audit log.** These actions are recorded with who, what, when and, where it applies, the values before and after:
  creating, editing, deactivating, reactivating a resident and resetting a password; complaint overrides;
  creating, editing and deleting fee-schedule items; billing runs; editing and deleting notices; report exports;
  and retrying failed deliveries. **There is no screen or API to read the audit log yet**; it is in the
  database (`audit_logs`).
- **History that is kept.** Room allocations are closed, not deleted. The fee ledger only grows. Complaint
  status changes are stored as events. Leave decisions store the approver, the note and the time. AI results
  are stored with the model, prompt version and outcome, including failures.
