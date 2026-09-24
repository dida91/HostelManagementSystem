"use client";

import { Dices } from "lucide-react";
import { useState } from "react";

import { Button, Checkbox, Field, fieldErrors, FieldRow, FormError, Input, Modal, Select, Textarea } from "@/components/ui";
import type { Student } from "@/lib/api/types";
import { todayISO } from "@/lib/format";
import { useCreateStudent, useDeactivateStudent, useResetPassword } from "@/lib/queries";
import { toast } from "@/lib/store";

import { generatePassword } from "./password";

export function RegisterModal({ onClose, onCreated }: { onClose: () => void; onCreated: (s: Student) => void }) {
  const create = useCreateStudent();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    student_code: "",
    initial_password: generatePassword(),
    phone: "",
    college: "",
    program: "",
    guardian_name: "",
    guardian_phone: "",
    admission_date: todayISO(),
  });
  const errors = fieldErrors(create.error);
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const valid =
    form.full_name.trim().length >= 2 && form.email.includes("@") && form.student_code.trim().length >= 2 && form.initial_password.length >= 10;
  const opt = (v: string) => v.trim() || null;
  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      busy={create.isPending}
      title="Register a student"
      description="Creates the resident's record and their sign-in. Give them the first password in person."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={create.isPending}
            disabled={!valid}
            onClick={() =>
              create.mutate(
                {
                  full_name: form.full_name.trim(),
                  email: form.email.trim(),
                  student_code: form.student_code.trim(),
                  initial_password: form.initial_password,
                  phone: opt(form.phone),
                  college: opt(form.college),
                  program: opt(form.program),
                  guardian_name: opt(form.guardian_name),
                  guardian_phone: opt(form.guardian_phone),
                  admission_date: form.admission_date || null,
                },
                {
                  onSuccess: (s) => {
                    toast.success("Student registered", `${s.full_name} can sign in with the password you gave them.`);
                    onCreated(s);
                  },
                },
              )
            }
          >
            Register student
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FieldRow>
          <Field label="Full name" htmlFor="st-name" required error={errors.full_name}>
            <Input id="st-name" value={form.full_name} onChange={(e) => set({ full_name: e.target.value })} />
          </Field>
          <Field label="Student code" htmlFor="st-code" required error={errors.student_code} help="As printed on the hostel card.">
            <Input id="st-code" value={form.student_code} onChange={(e) => set({ student_code: e.target.value })} placeholder="KH-2026-003" />
          </Field>
        </FieldRow>
        <FieldRow>
          <Field label="Email" htmlFor="st-email" required error={errors.email} help="Used to sign in.">
            <Input id="st-email" type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} />
          </Field>
          <Field label="Mobile" htmlFor="st-phone" error={errors.phone}>
            <Input id="st-phone" type="tel" value={form.phone} onChange={(e) => set({ phone: e.target.value })} placeholder="98XXXXXXXX" />
          </Field>
        </FieldRow>
        <Field label="First password" htmlFor="st-password" required error={errors.initial_password} help="At least 10 characters. They can change it after signing in.">
          <div className="flex gap-2">
            <Input id="st-password" value={form.initial_password} onChange={(e) => set({ initial_password: e.target.value })} className="font-medium tracking-wide" />
            <Button icon={Dices} onClick={() => set({ initial_password: generatePassword() })} aria-label="Generate a new password">
              New
            </Button>
          </div>
        </Field>
        <FieldRow>
          <Field label="College" htmlFor="st-college">
            <Input id="st-college" value={form.college} onChange={(e) => set({ college: e.target.value })} />
          </Field>
          <Field label="Program" htmlFor="st-program">
            <Input id="st-program" value={form.program} onChange={(e) => set({ program: e.target.value })} />
          </Field>
        </FieldRow>
        <FieldRow cols={3}>
          <Field label="Guardian" htmlFor="st-guardian">
            <Input id="st-guardian" value={form.guardian_name} onChange={(e) => set({ guardian_name: e.target.value })} />
          </Field>
          <Field label="Guardian's phone" htmlFor="st-guardian-phone">
            <Input id="st-guardian-phone" type="tel" value={form.guardian_phone} onChange={(e) => set({ guardian_phone: e.target.value })} />
          </Field>
          <Field label="Admitted on" htmlFor="st-admitted">
            <Input id="st-admitted" type="date" value={form.admission_date} onChange={(e) => set({ admission_date: e.target.value })} />
          </Field>
        </FieldRow>
        <FormError error={create.error} />
      </div>
    </Modal>
  );
}

export function ResetPasswordModal({ student, onClose }: { student: Student; onClose: () => void }) {
  const reset = useResetPassword(student.id);
  const [password, setPassword] = useState(generatePassword());
  return (
    <Modal
      open
      onClose={onClose}
      busy={reset.isPending}
      title={`New password for ${student.full_name}`}
      description="They're signed out everywhere and notified. Give them the new password in person."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={reset.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={reset.isPending}
            disabled={password.length < 10}
            onClick={() =>
              reset.mutate(password, {
                onSuccess: () => {
                  toast.success("Password reset", `${student.full_name} must use the new password now.`);
                  onClose();
                },
              })
            }
          >
            Reset password
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="New password" htmlFor="reset-password" help="At least 10 characters.">
          <div className="flex gap-2">
            <Input id="reset-password" value={password} onChange={(e) => setPassword(e.target.value)} className="font-medium tracking-wide" />
            <Button icon={Dices} onClick={() => setPassword(generatePassword())} aria-label="Generate a new password">
              New
            </Button>
          </div>
        </Field>
        <FormError error={reset.error} />
      </div>
    </Modal>
  );
}

export function DeactivateModal({ student, onClose }: { student: Student; onClose: () => void }) {
  const deactivate = useDeactivateStudent(student.id);
  const [status, setStatus] = useState<"ALUMNI" | "SUSPENDED">("ALUMNI");
  const [reason, setReason] = useState("");
  const [leaving, setLeaving] = useState(todayISO());
  const [vacate, setVacate] = useState(true);
  const alumni = status === "ALUMNI";
  return (
    <Modal
      open
      onClose={onClose}
      busy={deactivate.isPending}
      title={alumni ? `Check out ${student.full_name}?` : `Suspend ${student.full_name}?`}
      description="Sign-in stops immediately. Fees, complaints and leave history are kept."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={deactivate.isPending}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={deactivate.isPending}
            disabled={reason.trim().length < 3}
            onClick={() =>
              deactivate.mutate(
                { status, reason: reason.trim(), vacate_bed: alumni || vacate, leaving_date: leaving || null },
                {
                  onSuccess: (r) => {
                    toast.success(
                      alumni ? "Checked out" : "Suspended",
                      r.ended_assignment_id ? "Their bed is free again." : undefined,
                    );
                    onClose();
                  },
                },
              )
            }
          >
            {alumni ? "Check out" : "Suspend"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="What's happening" htmlFor="deactivate-status">
          <Select id="deactivate-status" value={status} onChange={(e) => setStatus(e.target.value as "ALUMNI")}>
            <option value="ALUMNI">Leaving the hostel (becomes alumni)</option>
            <option value="SUSPENDED">Suspended</option>
          </Select>
        </Field>
        <Field label="Reason" htmlFor="deactivate-reason" required help="Kept in the audit record.">
          <Textarea id="deactivate-reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        <Field label={alumni ? "Leaving on" : "Bed released on"} htmlFor="deactivate-date">
          <Input id="deactivate-date" type="date" value={leaving} onChange={(e) => setLeaving(e.target.value)} />
        </Field>
        {!alumni && (
          <Checkbox checked={vacate} onChange={(e) => setVacate(e.target.checked)} label="Free their bed" description="Leave unticked if they keep the bed during the suspension." />
        )}
        <FormError error={deactivate.error} />
      </div>
    </Modal>
  );
}
