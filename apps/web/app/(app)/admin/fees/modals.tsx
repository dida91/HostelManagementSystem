"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { StudentPicker } from "@/components/domain/student-picker";
import {
  Button,
  Field,
  fieldErrors,
  FieldRow,
  FormError,
  IconButton,
  Input,
  Modal,
  Select,
  Textarea,
} from "@/components/ui";
import type { FeeStructure, InvoiceGeneration, Student } from "@/lib/api/types";
import { currentPeriod, formatDate, npr, periodLabel, recentPeriods, todayISO } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import {
  useCreateInvoice,
  useCreateStructure,
  useGenerateInvoices,
  useInvoices,
  useRecordPayment,
  useStudent,
  useUpdateStructure,
} from "@/lib/queries";
import { toast } from "@/lib/store";

const UNPAID = ["ISSUED", "PARTIALLY_PAID", "OVERDUE"];

function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function PaymentModal({
  preset,
  onClose,
}: {
  preset?: { studentId: string; invoiceId: string; amount: string };
  onClose: () => void;
}) {
  const record = useRecordPayment();
  // One key per payment attempt: a retry or double click can't record it twice.
  const [key] = useState(() => crypto.randomUUID());
  const presetStudent = useStudent(preset?.studentId);
  const [picked, setPicked] = useState<Student | null>(null);
  const student = picked ?? presetStudent.data ?? null;
  const [invoiceId, setInvoiceId] = useState(preset?.invoiceId ?? "");
  const [amount, setAmount] = useState(preset ? String(Number(preset.amount)) : "");
  const [method, setMethod] = useState("CASH");
  const [reference, setReference] = useState("");
  const [paidAt, setPaidAt] = useState(nowLocal());
  const invoices = useInvoices({ student_id: student?.id, limit: 50 }, !!student);
  const unpaid = (invoices.data?.items ?? []).filter((i) => UNPAID.includes(i.status));
  const errors = fieldErrors(record.error);
  const valid = student && Number(amount) > 0;

  return (
    <Modal
      open
      onClose={onClose}
      busy={record.isPending}
      title="Record a payment"
      description="Adds a credit to the resident's account. They get a receipt notification."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={record.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={record.isPending}
            disabled={!valid}
            onClick={() =>
              student &&
              record.mutate(
                {
                  key,
                  body: {
                    student_id: student.id,
                    amount_npr: amount,
                    method: method as "CASH",
                    invoice_id: invoiceId || null,
                    reference_no: reference.trim() || null,
                    paid_at: new Date(paidAt).toISOString(),
                  },
                },
                {
                  onSuccess: () => {
                    toast.success("Payment recorded", `${npr(amount)} from ${student.full_name}.`);
                    onClose();
                  },
                },
              )
            }
          >
            Record payment
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Resident" htmlFor="pay-student" required>
          <StudentPicker
            id="pay-student"
            value={student}
            onChange={(s) => {
              setPicked(s);
              setInvoiceId("");
            }}
          />
        </Field>
        <Field label="Towards invoice" htmlFor="pay-invoice" help="Optional. Settles that invoice when fully paid.">
          <Select
            id="pay-invoice"
            value={invoiceId}
            disabled={!student}
            onChange={(e) => {
              setInvoiceId(e.target.value);
              const inv = unpaid.find((i) => i.id === e.target.value);
              if (inv && !amount && inv.total_npr) setAmount(String(Number(inv.total_npr)));
            }}
          >
            <option value="">General payment on account</option>
            {unpaid.map((i) => (
              <option key={i.id} value={i.id}>
                {i.invoice_number}, due {formatDate(i.due_date)} ({npr(i.total_npr)})
              </option>
            ))}
          </Select>
        </Field>
        <FieldRow>
          <Field label="Amount (NPR)" htmlFor="pay-amount" required error={errors.amount_npr}>
            <Input id="pay-amount" type="number" min={1} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label="Paid by" htmlFor="pay-method">
            <Select id="pay-method" value={method} onChange={(e) => setMethod(e.target.value)}>
              {OPTIONS.paymentMethod.map((m) => (
                <option key={m} value={m}>
                  {label(m)}
                </option>
              ))}
            </Select>
          </Field>
        </FieldRow>
        <FieldRow>
          <Field label="Reference" htmlFor="pay-ref" help="Receipt or transaction number.">
            <Input id="pay-ref" maxLength={120} value={reference} onChange={(e) => setReference(e.target.value)} />
          </Field>
          <Field label="Received" htmlFor="pay-at">
            <Input id="pay-at" type="datetime-local" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} />
          </Field>
        </FieldRow>
        <FormError error={record.error} />
      </div>
    </Modal>
  );
}

interface Line {
  description: string;
  quantity: string;
  amount: string;
}

export function InvoiceModal({ onClose }: { onClose: () => void }) {
  const create = useCreateInvoice();
  const [student, setStudent] = useState<Student | null>(null);
  const month = currentPeriod();
  const [form, setForm] = useState({ period_start: `${month}-01`, period_end: todayISO(), due_date: todayISO(7), note: "" });
  const [lines, setLines] = useState<Line[]>([{ description: "", quantity: "1", amount: "" }]);
  const total = lines.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.amount || 0), 0);
  const validLines = lines.every((l) => l.description.trim() && Number(l.quantity) > 0 && Number(l.amount) >= 0);
  const valid = student && validLines && total > 0 && form.period_end >= form.period_start;
  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      busy={create.isPending}
      title="Issue an invoice"
      description="For one-off charges. Monthly rent and fees are billed automatically on the 1st."
      footer={
        <>
          <span className="mr-auto self-center text-ui text-mist">
            Total <span className="t-sub text-snow tabular">{npr(total)}</span>
          </span>
          <Button variant="ghost" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            disabled={!valid}
            onClick={() =>
              student &&
              create.mutate(
                {
                  student_id: student.id,
                  ...form,
                  note: form.note.trim() || null,
                  line_items: lines.map((l) => ({
                    description: l.description.trim(),
                    quantity: l.quantity,
                    unit_amount_npr: l.amount,
                  })),
                },
                {
                  onSuccess: (inv) => {
                    toast.success("Invoice issued", `${inv.invoice_number} for ${student.full_name}.`);
                    onClose();
                  },
                },
              )
            }
          >
            Issue invoice
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <Field label="Resident" htmlFor="inv-student" required>
          <StudentPicker id="inv-student" value={student} onChange={setStudent} />
        </Field>
        <FieldRow cols={3}>
          <Field label="Period from" htmlFor="inv-from">
            <Input id="inv-from" type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
          </Field>
          <Field label="Period to" htmlFor="inv-to" error={form.period_end < form.period_start ? "Can't end before it starts." : null}>
            <Input id="inv-to" type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
          </Field>
          <Field label="Due" htmlFor="inv-due">
            <Input id="inv-due" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          </Field>
        </FieldRow>
        <fieldset className="space-y-2">
          <legend className="mb-1.5 text-ui font-medium text-snow/90">Charges</legend>
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-[minmax(0,1fr)_4.5rem_8rem_auto] items-center gap-2">
              <Input aria-label={`Charge ${i + 1} description`} placeholder="Replacement key" value={l.description} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
              <Input aria-label={`Charge ${i + 1} quantity`} type="number" min={1} value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} />
              <Input aria-label={`Charge ${i + 1} amount in NPR`} type="number" min={0} step="0.01" placeholder="NPR" value={l.amount} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))} />
              <IconButton icon={Trash2} label={`Remove charge ${i + 1}`} size="sm" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))} />
            </div>
          ))}
          <Button size="sm" variant="ghost" icon={Plus} onClick={() => setLines([...lines, { description: "", quantity: "1", amount: "" }])}>
            Add a charge
          </Button>
        </fieldset>
        <Field label="Note" htmlFor="inv-note" help="Shown to the resident on the invoice.">
          <Textarea id="inv-note" rows={2} maxLength={1000} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </Field>
        <FormError error={create.error} />
      </div>
    </Modal>
  );
}

export function GenerateModal({ onClose }: { onClose: () => void }) {
  const generate = useGenerateInvoices();
  const [period, setPeriod] = useState(currentPeriod());
  const [dueDay, setDueDay] = useState("");
  const [result, setResult] = useState<InvoiceGeneration | null>(null);
  const day = Number(dueDay);
  const dueDate = Number.isInteger(day) && day >= 1 && day <= 28 ? `${period}-${String(day).padStart(2, "0")}` : "";
  const pastDue = dueDate !== "" && dueDate < todayISO();
  return (
    <Modal
      open
      onClose={onClose}
      busy={generate.isPending}
      title="Bill a month"
      description="Invoices every resident for room rent plus the monthly fees in effect. Runs by itself on the 1st; residents already billed for the month are skipped."
      footer={
        result ? (
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose} disabled={generate.isPending}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={generate.isPending}
              disabled={!period}
              onClick={() =>
                generate.mutate(
                  { period, dueDay: dueDay ? Number(dueDay) : undefined },
                  {
                    onSuccess: (r) => {
                      setResult(r);
                      toast.success(`${r.created} ${r.created === 1 ? "invoice" : "invoices"} issued`, periodLabel(r.billing_period));
                    },
                  },
                )
              }
            >
              Bill {period ? periodLabel(period) : "month"}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <ul className="space-y-2 text-body">
          <li className="flex justify-between">
            <span className="text-mist">Invoices issued</span>
            <span className="text-snow tabular">{result.created}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-mist">Already billed for {periodLabel(result.billing_period)}</span>
            <span className="text-snow tabular">{result.skipped_existing}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-mist">Nothing to charge (no rent or fees set)</span>
            <span className="text-snow tabular">{result.skipped_no_charges}</span>
          </li>
        </ul>
      ) : (
        <div className="space-y-4">
          <FieldRow>
            <Field label="Month" htmlFor="gen-month">
              <Select id="gen-month" value={period} onChange={(e) => setPeriod(e.target.value)}>
                {recentPeriods().map((p) => (
                  <option key={p} value={p}>
                    {periodLabel(p)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Due on day"
              htmlFor="gen-due"
              help={
                pastDue ? (
                  <span className="text-marigold-300">
                    {formatDate(dueDate)} has already passed, so these invoices would be overdue straight away. Pick a later day.
                  </span>
                ) : (
                  "Leave empty for the usual due day."
                )
              }
            >
              <Input id="gen-due" type="number" min={1} max={28} value={dueDay} onChange={(e) => setDueDay(e.target.value)} />
            </Field>
          </FieldRow>
          <FormError error={generate.error} />
        </div>
      )}
    </Modal>
  );
}

export function StructureModal({ structure, onClose }: { structure: FeeStructure | null; onClose: () => void }) {
  const create = useCreateStructure();
  const update = useUpdateStructure();
  const mutation = structure ? update : create;
  const [form, setForm] = useState({
    name: structure?.name ?? "",
    description: structure?.description ?? "",
    amount_npr: structure ? String(Number(structure.amount_npr)) : "",
    cadence: structure?.cadence ?? "MONTHLY",
    effective_from: structure?.effective_from ?? `${currentPeriod()}-01`,
    effective_to: structure?.effective_to ?? "",
  });
  const errors = fieldErrors(mutation.error);
  const badWindow = form.effective_to && form.effective_to < form.effective_from;
  const valid = form.name.trim().length >= 2 && form.amount_npr !== "" && Number(form.amount_npr) >= 0 && !badWindow;
  const submit = () => {
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      amount_npr: form.amount_npr,
      cadence: form.cadence as "MONTHLY",
      effective_from: form.effective_from,
      effective_to: form.effective_to || null,
    };
    const done = () => {
      toast.success(structure ? "Fee updated" : "Fee added", body.name);
      onClose();
    };
    if (structure) update.mutate({ id: structure.id, body }, { onSuccess: done });
    else create.mutate(body, { onSuccess: done });
  };
  return (
    <Modal
      open
      onClose={onClose}
      busy={mutation.isPending}
      title={structure ? `Edit ${structure.name}` : "Add a fee"}
      description="Monthly fees are billed with room rent on the 1st. Issued invoices keep their original amounts."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button variant="primary" loading={mutation.isPending} disabled={!valid} onClick={submit}>
            {structure ? "Save fee" : "Add fee"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FieldRow>
          <Field label="Name" htmlFor="fee-name" required error={errors.name}>
            <Input id="fee-name" maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Mess fee" />
          </Field>
          <Field label="Amount (NPR)" htmlFor="fee-amount" required error={errors.amount_npr}>
            <Input id="fee-amount" type="number" min={0} step="0.01" value={form.amount_npr} onChange={(e) => setForm({ ...form, amount_npr: e.target.value })} />
          </Field>
        </FieldRow>
        <Field label="How often" htmlFor="fee-cadence">
          <Select id="fee-cadence" value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })}>
            <option value="MONTHLY">Every month (billed automatically)</option>
            <option value="ONE_TIME">One-time (add it to an invoice by hand)</option>
          </Select>
        </Field>
        <FieldRow>
          <Field label="In effect from" htmlFor="fee-from">
            <Input id="fee-from" type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
          </Field>
          <Field label="Until" htmlFor="fee-to" help="Leave empty to keep it going." error={badWindow ? "Can't end before it starts." : errors.effective_to}>
            <Input id="fee-to" type="date" value={form.effective_to} onChange={(e) => setForm({ ...form, effective_to: e.target.value })} />
          </Field>
        </FieldRow>
        <Field label="Description" htmlFor="fee-description">
          <Textarea id="fee-description" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <FormError error={mutation.error} />
      </div>
    </Modal>
  );
}
