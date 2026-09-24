"use client";

import { KeyRound, Pencil, UserCheck, UserX } from "lucide-react";
import { useState } from "react";

import {
  Button,
  ConfirmDialog,
  Details,
  Drawer,
  EnumPill,
  ErrorState,
  Field,
  fieldErrors,
  FieldRow,
  FormError,
  Input,
  Kpi,
  Money,
  SkeletonLines,
  Tag,
  Textarea,
} from "@/components/ui";
import type { Me, Student, StudentUpdate } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { can } from "@/lib/permissions";
import { useBalance, useReactivateStudent, useStudent, useUpdateStudent } from "@/lib/queries";
import { toast } from "@/lib/store";

import { DeactivateModal, ResetPasswordModal } from "./modals";

const FIELDS: [keyof StudentUpdate, string, string?][] = [
  ["full_name", "Full name"],
  ["email", "Email", "email"],
  ["phone", "Mobile", "tel"],
  ["college", "College"],
  ["program", "Program"],
  ["guardian_name", "Guardian"],
  ["guardian_relation", "Relation to resident"],
  ["guardian_phone", "Guardian's phone", "tel"],
  ["emergency_contact", "Emergency contact", "tel"],
  ["admission_date", "Admitted on", "date"],
  ["date_of_birth", "Date of birth", "date"],
];

function EditForm({ student, onDone }: { student: Student; onDone: () => void }) {
  const update = useUpdateStudent(student.id);
  const initial = Object.fromEntries(
    [...FIELDS.map(([k]) => k), "permanent_address"].map((k) => [k, String((student as Record<string, unknown>)[k] ?? "")]),
  ) as Record<string, string>;
  const [form, setForm] = useState(initial);
  const errors = fieldErrors(update.error);
  const changed = Object.fromEntries(
    Object.entries(form)
      .filter(([k, v]) => v !== initial[k])
      .map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]),
  ) as StudentUpdate;
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate(changed, {
          onSuccess: () => {
            toast.success("Profile updated", student.full_name);
            onDone();
          },
        });
      }}
    >
      {FIELDS.reduce<[keyof StudentUpdate, string, string?][][]>((rows, f, i) => {
        if (i % 2 === 0) rows.push([f]);
        else rows[rows.length - 1].push(f);
        return rows;
      }, []).map((row) => (
        <FieldRow key={row[0][0]}>
          {row.map(([key, text, type]) => (
            <Field key={key} label={text} htmlFor={`edit-${key}`} error={errors[key]}>
              <Input id={`edit-${key}`} type={type ?? "text"} value={form[key]} invalid={!!errors[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            </Field>
          ))}
        </FieldRow>
      ))}
      <Field label="Home address" htmlFor="edit-address">
        <Textarea id="edit-address" rows={2} value={form.permanent_address} onChange={(e) => setForm({ ...form, permanent_address: e.target.value })} />
      </Field>
      <FormError error={update.error} />
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onDone} disabled={update.isPending}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={update.isPending} disabled={Object.keys(changed).length === 0}>
          Save profile
        </Button>
      </div>
    </form>
  );
}

export function StudentDrawer({ id, me, onClose }: { id: string | null; me: Me; onClose: () => void }) {
  const student = useStudent(id);
  const balance = useBalance(id ?? undefined, !!id);
  const reactivate = useReactivateStudent(id ?? "");
  const [editing, setEditing] = useState(false);
  const [modal, setModal] = useState<"reset" | "deactivate" | "reactivate" | null>(null);
  const s = student.data;
  const lifecycle = can(me.role, "studentLifecycle");
  const inactive = s && (!s.is_active || s.status === "ALUMNI" || s.status === "SUSPENDED");

  return (
    <>
      <Drawer
        open={!!id && !modal}
        onClose={() => {
          setEditing(false);
          onClose();
        }}
        title={s?.full_name ?? "Resident"}
        description={
          s && (
            <span className="flex flex-wrap items-center gap-2">
              {s.student_code}
              <EnumPill domain="studentStatus" value={s.status} />
              {!s.is_active && <Tag>Sign-in off</Tag>}
            </span>
          )
        }
        footer={
          s && !editing ? (
            <>
              {lifecycle &&
                (inactive ? (
                  <Button icon={UserCheck} className="mr-auto" onClick={() => setModal("reactivate")}>
                    Reactivate
                  </Button>
                ) : (
                  <Button variant="ghost" icon={UserX} className="mr-auto" onClick={() => setModal("deactivate")}>
                    Check out or suspend
                  </Button>
                ))}
              {lifecycle && (
                <Button icon={KeyRound} onClick={() => setModal("reset")}>
                  Reset password
                </Button>
              )}
              <Button variant="primary" icon={Pencil} onClick={() => setEditing(true)}>
                Edit profile
              </Button>
            </>
          ) : undefined
        }
      >
        {student.isError ? (
          <ErrorState error={student.error} onRetry={() => student.refetch()} />
        ) : !s ? (
          <SkeletonLines lines={8} />
        ) : editing ? (
          <EditForm student={s} onDone={() => setEditing(false)} />
        ) : (
          <div className="space-y-7">
            <div className="grid grid-cols-2 gap-3">
              <Kpi
                label="Fees outstanding"
                loading={balance.isPending}
                value={balance.data ? <Money value={balance.data.outstanding} whole /> : "—"}
                className="p-4"
              />
              <Kpi label="Room" value={<span className="text-heading">{s.room ?? "No bed"}</span>} className="p-4" />
            </div>
            <Details
              items={[
                ["Email", s.email],
                ["Mobile", s.phone ?? "—"],
                ["College", s.college ?? "—"],
                ["Program", s.program ?? "—"],
                ["Admitted", formatDate(s.admission_date)],
                ["Date of birth", formatDate(s.date_of_birth)],
              ]}
            />
            <section>
              <h3 className="t-sub mb-3">Guardian and emergency</h3>
              <Details
                items={[
                  ["Guardian", s.guardian_name ? `${s.guardian_name}${s.guardian_relation ? ` (${s.guardian_relation})` : ""}` : "—"],
                  ["Guardian's phone", s.guardian_phone ?? "—"],
                  ["Emergency contact", s.emergency_contact ?? "—"],
                  ["Home address", s.permanent_address ?? "—"],
                ]}
              />
            </section>
          </div>
        )}
      </Drawer>
      {s && modal === "reset" && <ResetPasswordModal student={s} onClose={() => setModal(null)} />}
      {s && modal === "deactivate" && <DeactivateModal student={s} onClose={() => setModal(null)} />}
      <ConfirmDialog
        open={modal === "reactivate"}
        onClose={() => setModal(null)}
        title={`Reactivate ${s?.full_name ?? "resident"}?`}
        confirmLabel="Reactivate"
        loading={reactivate.isPending}
        onConfirm={() =>
          reactivate.mutate(undefined, {
            onSuccess: () => {
              toast.success("Reactivated", "They can sign in again. Allocate a bed from Rooms if they're moving back in.");
              setModal(null);
            },
            onError: (e) => toast.error("Not reactivated", e.message),
          })
        }
      >
        <p>They become an active resident and can sign in again. A bed isn’t allocated automatically.</p>
      </ConfirmDialog>
    </>
  );
}
