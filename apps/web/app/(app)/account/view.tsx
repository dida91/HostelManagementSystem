"use client";

import { KeyRound } from "lucide-react";
import { useState } from "react";

import { Avatar, Button, Checkbox, Details, Field, FormError, Input, PageHeader, Panel, SkeletonLines } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { roleLabel } from "@/lib/permissions";
import { useChangePassword, useMe, useStudent } from "@/lib/queries";
import { toast, usePrefs } from "@/lib/store";

function PasswordForm() {
  const change = useChangePassword();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [touched, setTouched] = useState(false);
  const short = form.next.length > 0 && form.next.length < 10;
  const mismatch = form.confirm.length > 0 && form.confirm !== form.next;
  return (
    <Panel title="Change password" description="Use at least 10 characters. Other devices are signed out when it changes.">
      <form
        className="max-w-md space-y-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (!form.current || form.next.length < 10 || form.next !== form.confirm) return;
          change.mutate(
            { current: form.current, next: form.next },
            {
              onSuccess: () => {
                setForm({ current: "", next: "", confirm: "" });
                setTouched(false);
                toast.success("Password changed", "Other devices were signed out.");
              },
            },
          );
        }}
      >
        <Field label="Current password" htmlFor="pw-current" error={touched && !form.current ? "Enter your current password." : null}>
          <Input id="pw-current" type="password" autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
        </Field>
        <Field label="New password" htmlFor="pw-next" error={short || (touched && form.next.length < 10) ? "Use at least 10 characters." : null}>
          <Input id="pw-next" type="password" autoComplete="new-password" value={form.next} invalid={short} onChange={(e) => setForm({ ...form, next: e.target.value })} />
        </Field>
        <Field label="Type it again" htmlFor="pw-confirm" error={mismatch ? "The two passwords don't match." : null}>
          <Input id="pw-confirm" type="password" autoComplete="new-password" value={form.confirm} invalid={mismatch} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
        </Field>
        <FormError error={change.error} />
        <Button type="submit" variant="primary" icon={KeyRound} loading={change.isPending}>
          Change password
        </Button>
      </form>
    </Panel>
  );
}

export function AccountView() {
  const { data: me } = useMe();
  const student = useStudent(me?.student_id);
  const reduceEffects = usePrefs((s) => s.reduceEffects);
  const setReduceEffects = usePrefs((s) => s.setReduceEffects);
  if (!me) return null;
  return (
    <>
      <PageHeader title="Account" description="Your sign-in details and how the portal behaves on this device." />
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Panel title="Profile">
          <div className="mb-6 flex items-center gap-4">
            <Avatar name={me.full_name} size="lg" />
            <div>
              <p className="t-heading">{me.full_name}</p>
              <p className="text-ui text-mist">{roleLabel(me.role)}</p>
            </div>
          </div>
          {me.student_id && student.isPending ? (
            <SkeletonLines lines={4} />
          ) : (
            <Details
              items={[
                ["Email", me.email],
                ...(me.student_code ? ([["Student code", me.student_code]] as [string, string][]) : []),
                ...(student.data
                  ? ([
                      ["Room", student.data.room ?? "No bed allocated"],
                      ["College", student.data.college ?? "—"],
                      ["Program", student.data.program ?? "—"],
                      ["Admitted", formatDate(student.data.admission_date)],
                    ] as [string, string][])
                  : []),
              ]}
            />
          )}
          {me.student_id && (
            <p className="mt-6 text-small text-stone">To correct any of these, ask the hostel office.</p>
          )}
        </Panel>
        <div className="space-y-5">
          <PasswordForm />
          <Panel title="On this device">
            <Checkbox
              checked={reduceEffects}
              onChange={(e) => setReduceEffects(e.target.checked)}
              label="Reduce motion and effects"
              description="Keeps the mountain scene still and turns off animations. Useful on older phones."
            />
          </Panel>
        </div>
      </div>
    </>
  );
}
