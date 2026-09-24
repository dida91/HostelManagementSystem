# Project overview: why this system exists

**AI-Powered Smart Hostel Management and Data Analytics System**
Partner hostel: Kutumba 1 Girls Hostel, Pokhara, Nepal.

This page explains the problem the project solves, who it helps, how it helps, and
what it deliberately does not do. For the list of functions see
[02-features.md](02-features.md); to run it see [03-getting-started.md](03-getting-started.md).

> **About the examples.** The problems below are the ones residential hostels of this
> kind commonly face, and the system is designed around them. They are not a record of
> how Kutumba works today. Before presenting this to the hostel, replace or confirm
> them with the warden's own examples.

---

## 1. What it is, in one paragraph

A web application that puts the everyday running of a hostel in one place. Residents
sign in to report problems, ask for leave, see their fees, read notices, rate meals and
ask questions. The warden and staff sign in to register residents, allocate beds,
handle complaints, approve leave, bill and record payments, publish notices and see how
the hostel is doing. An AI assistant (Google Gemini) helps in a few specific ways: it suggests
how to sort a complaint, summarises meal feedback, answers questions about a resident's
own fees, leave and room, answers "what do the rules say?" from the hostel's own
documents, and writes a plain-language briefing from the analytics. People make every
decision; the AI only advises.

![The sign-in page](images/login.png)

---

## 2. The problem

Running a hostel means running several processes at the same time, each of which
involves people's money, safety or daily comfort. When they are kept in paper
registers, spreadsheets and chat groups, the same failures keep appearing:

| Area | What typically goes wrong |
|---|---|
| **Who lives where** | The bed register and the spreadsheet disagree. Two residents are promised the same bed. Nobody can say who lived in a room last term. |
| **Fees** | Monthly billing is manual and slow. Receipts are handwritten. A resident says they paid; the office cannot prove otherwise. Reminders depend on someone remembering. |
| **Complaints** | Problems arrive by word of mouth, phone or chat. Urgent ones (an unsafe gate, no water) sit among routine ones. Nobody tracks what happened, and the resident is never told. Many are written in Nepali or a mix of Nepali and English. |
| **Leave and safety** | Permission to go home or stay out is verbal or on loose paper. The warden cannot quickly say who is away tonight or whether the guardian agreed. In a girls' hostel this is a safety question, not paperwork. |
| **Meals** | The menu changes by announcement. Feedback is anecdotal ("the food is bad") with nothing to act on. |
| **Notices** | Announcements in a chat group scroll away. New residents never see old ones. |
| **Rules** | The same questions ("When does the gate close?", "How do I apply for leave?") are asked of the warden again and again. |
| **Oversight** | Owners and inspectors ask for reports. Producing them means hours of copying. There is no data to show trends such as which problems recur or how many beds are empty. |
| **Privacy** | Personal details of young residents sit in loose files and chat histories that anyone can forward. |

---

## 3. How the system answers each problem

| Problem | What the system does | Where to find it |
|---|---|---|
| Who lives where | Blocks, rooms and beds are recorded, and the database itself refuses to give one bed to two residents or two beds to one resident. Moving out closes the record; it is never erased, so history stays. A 3D model of the blocks shows what is full or empty at a glance. | Rooms, Students |
| Fees | A fee schedule plus each room's rent produce every resident's monthly invoice automatically on the 1st (or with one click). Payments are recorded against invoices, part payments are supported, reminders and overdue marking run by themselves, and each resident sees their own statement. Every balance is added up from an append-only ledger; nobody types a balance in. | Fees |
| Complaints | Residents write in their own words, in English or Nepali. The AI suggests a category, a priority and a department, and flags anything about safety, security, harassment or health as urgent. Staff see the most urgent first, can change anything the AI suggested, and the resident is notified when the status changes. | Complaints |
| Leave and safety | A resident requests leave with dates, destination and whether their guardian agrees. The warden approves or rejects with a note, the resident is notified, and approved leave completes by itself after the return date. A leave register can be exported. | Leave, Reports |
| Meals | The weekly menu is editable by staff and visible to residents. Residents rate each meal from 1 to 5 and can comment; the AI summarises comments into mood and issues, and average ratings appear by meal. | Mess, Analytics |
| Notices | The warden posts notices for everyone, residents only or staff only, can schedule them for later and set an expiry. Recipients get an in-app notification (and an email if email is set up). | Notices |
| Rules | The warden uploads the hostel's rules and policies. Residents and staff ask questions and get an answer with citations to the source document. If the documents do not cover the question, the assistant says so instead of guessing. | Assistant, Documents |
| Oversight | Excel and PDF reports for residents, occupancy, fees, complaints and leave (Nepali prints correctly in PDFs when the server has a Devanagari font). An analytics page shows occupancy, complaints by category and status, time to resolve, fees collected and mess ratings, with an optional plain-language AI briefing. | Reports, Analytics |
| Privacy | Every screen and every API call is checked against the person's role. A resident can only ever see their own records, and the assistant is built so that it cannot ask for anyone else's. Complaint reports leave out who filed each complaint. Key administrative changes (resident records, complaint overrides, the fee schedule, billing runs, report exports) are written to an audit log. | Everywhere |

![The warden's home screen: what needs attention today](images/office-home.png)

---

## 4. Who benefits, and how

**Residents**
- One place to report a problem, ask for leave, check what they owe and read notices.
- Their own figures are always current, and they match what the office sees.
- They are told when something changes: a complaint moves, leave is decided, a payment
  is recorded, a bed is allocated.
- They can ask the assistant about their own fees, leave and room, or about the rules, at
  any hour, in English or Nepali.
- It works on a phone.

**Warden**
- A home screen that starts with what needs attention: open complaints, most urgent first,
  and leave waiting for a decision.
- Decisions are recorded with the note and the time, so there is a trail.
- Billing, reminders and overdue tracking run on their own.
- Reports for owners or inspectors take a click instead of an afternoon.
- Only the warden can do the sensitive things: decide leave, deactivate a resident,
  reset a password, manage rooms, fees and notices, and export personal-data reports.

**Office staff**
- Register residents, allocate and vacate beds, triage complaints, issue invoices,
  record payments and update the menu, without access to the warden-only actions.

**Hostel owner or management**
- Trends instead of impressions: occupancy, recurring problem areas, how long problems
  take to fix, fee collection and how the food is rated.
- An audit trail of who changed what.

**Guardians** are not users of the system. Their details are recorded, and a resident
states on each leave request whether their guardian agrees, which gives the warden a
clearer picture. There is no guardian portal.

---

## 5. A day in the hostel with the system

| When | What happens |
|---|---|
| 1st of the month, 06:00 | Invoices for the month are created for every resident holding a bed. Each resident is notified. |
| A few days before the due date | Residents with unpaid invoices get a reminder. After the due date the invoice is marked overdue and the resident is told once. |
| 21:40, a resident writes a complaint in Nepali about a loose door lock | It is saved at once. In the background the AI proposes a category, priority and department. |
| Next morning | The warden's home screen lists open complaints, most urgent first. The warden sets the priority, sends it to maintenance and marks it in progress. The resident is notified of the new status. |
| Midday | A resident asks for leave for a family wedding and says their guardian agrees. The warden approves it with a note. The resident is notified; after the return date the leave completes itself. |
| Afternoon | A resident pays cash at the office. Staff record the payment against the invoice; the balance updates and the resident is notified. |
| Evening | The warden posts a notice about a water-tank cleaning. It goes to residents' inboxes. |
| Any time | A resident asks the assistant "How much do I owe?" or "When does the gate close?" and gets an answer taken from their own records or from the hostel's rulebook. |

---

## 6. Design principles

These are the decisions that shape the whole system. The reasoning for the first three is
written down in [`docs/adr/`](adr/).

1. **Numbers come from the database, never from the AI.** A resident's balance is
   calculated by adding up their ledger. Occupancy is a count of allocations. The AI may
   describe a number; it is never asked to produce one. A fluent wrong figure is worse
   than none. *(ADR 0003)*
2. **The AI advises; people decide.** Complaint suggestions are proposals that staff
   can override, and both the AI's suggestion and the staff decision are kept. The
   assistant can read and explain but cannot create or change anything.
3. **A resident can only see their own data, and the AI cannot be talked out of that.**
   The assistant's tools carry no "whose data?" parameter at all; the server supplies the
   signed-in person. So even a malicious message or a booby-trapped document cannot make
   it reveal another resident's information. *(ADR 0002)*
4. **Nothing important is silently erased.** Residency history, the fee ledger,
   complaint status changes and the audit log are kept: records are closed or added to,
   never deleted.
5. **It keeps working when the extras do not.** With no Gemini key the AI features
   report "unavailable" and everything else runs. With no email server, notifications
   still appear in the app. There is no fake sender or stub that pretends to work.
6. **English and Nepali.** Complaints and questions can be written in either; PDF
   reports print Devanagari correctly.
7. **A small footprint.** One database (PostgreSQL, which also stores the document search
   index), one cache/queue (Redis), and three processes. Nothing outside the machine is
   needed except the optional extras: the Gemini API, and an email server or SMS provider
   if you want those.

---

## 7. What the system does not do

Knowing the edges avoids wrong expectations.

- **It does not take online payments.** Staff record payments (cash, bank transfer,
  eSewa, Khalti or cheque) after they happen. There is no payment-gateway integration.
- **No guardian portal, visitor log, attendance or biometric check-in, maintenance
  work-order tracking or inventory.**
- **One hostel.** The name and the AI prompts are written for Kutumba 1 Girls Hostel.
  Blocks and rooms are supported, but there is no multi-hostel mode.
- **No native mobile app.** The website is designed to work on phones.
- **SMS is switched off.** The Sparrow SMS integration exists but has not been tried
  against a live account, so it is disabled by default. Email is optional and also off
  until configured. In-app notifications always work.
- **The AI does not act.** It cannot approve leave, change a fee or reassign a bed.

---

## 8. Where the project stands

**Working and tested (in development):** all the functions in
[02-features.md](02-features.md), 132 automated backend tests, and hands-on browser
checks of the web interface as both a resident and the warden, using synthetic sample
data.

**Not done yet, and worth knowing before a real launch:**

- It has **not been deployed or piloted with real residents.** Everything so far ran on
  a development machine with made-up data.
- **AI accuracy has not been measured.** A test harness and labelled example sets exist
  in [`ai/evaluation/`](../ai/evaluation/) but no results have been recorded, so no
  accuracy is claimed anywhere. Treat AI suggestions as suggestions.
- **The Gemini free tier is small.** Google limits how many AI requests a free key may
  make per day (about 20 per model when this was last checked in September 2026). That
  is enough to try the system and too little for daily use; a real deployment needs a paid
  key. Nothing else in the system depends on it.
- **Data leaves the hostel when AI is on.** Complaint text, mess comments, assistant
  questions, the resident's own record values that the assistant looks up, uploaded rule
  documents and summary statistics are sent to Google's Gemini API. Read Google's current
  terms for the tier you use (free and paid tiers handle submitted data differently)
  and get the hostel's agreement before using real resident data. With AI switched off
  nothing is sent.
- **There is no screen for creating staff or extra warden accounts.** Residents are
  registered in the app; the first warden comes from the seed script. See
  [03-getting-started.md](03-getting-started.md#adding-a-staff-or-warden-account).
- Other known gaps are listed in
  [05-technical-reference.md](05-technical-reference.md#known-limitations).

---

## 9. Words used in this documentation

| Word | Meaning |
|---|---|
| **Resident** | A person living in the hostel. In the database and API a resident is called a "student". |
| **Warden** | The person in charge of the hostel. Has every permission. |
| **Staff** | Office staff with day-to-day permissions but not the sensitive ones. |
| **Administrator** | A `SUPER_ADMIN` account. Today it has the same permissions as the warden. |
| **Block, room, bed** | Hostel layout. A room belongs to a block and has one or more beds (A, B, C...). |
| **Allocation** | Giving a resident a bed from a start date. Vacating ends it; the record stays. |
| **Invoice** | A bill for one period with line items. |
| **Ledger** | The append-only list of charges (debits) and payments (credits) per resident. The balance is the sum. |
| **Triage** | Sorting complaints by category, priority and who should deal with them. |
| **Notification** | A message inside the app. It can also go out by email. |
| **Assistant** | The AI chat page. "Your records" mode looks up the signed-in person's own data; "Rules and policies" mode answers from uploaded documents. |
| **RAG** | Retrieval-augmented generation: finding the relevant passages of the hostel's documents first, then answering only from them. |
| **Worker** | The background process that sends email, runs the AI, indexes documents and runs the scheduled jobs. |
