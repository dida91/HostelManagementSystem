"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";

const TYPES = ["HOME_VISIT", "MEDICAL", "ACADEMIC", "EMERGENCY", "OTHER"];

export default function LeavePage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  const { data } = useQuery({ queryKey: ["leave"], queryFn: api.listLeave });
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    leave_type: "HOME_VISIT",
    from_date: "",
    to_date: "",
    reason: "",
    guardian_consent: false,
  });

  const create = useMutation({
    mutationFn: () => api.createLeave(form),
    onSuccess: () => {
      setForm({ ...form, from_date: "", to_date: "", reason: "" });
      setError(null);
      qc.invalidateQueries({ queryKey: ["leave"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit."),
  });

  const decide = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.decideLeave(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave"] }),
  });

  const isStaff = me && me.role !== "STUDENT";

  return (
    <Shell>
      <h1 className="mb-6 text-xl font-semibold text-slate-800">Leave</h1>

      {!isStaff && (
        <div className="mb-6">
          <Card title="Request leave">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                create.mutate();
              }}
              className="space-y-3"
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="text-xs">
                  <span className="mb-1 block font-medium text-slate-600">Type</span>
                  <select
                    value={form.leave_type}
                    onChange={(e) => setForm({ ...form, leave_type: e.target.value })}
                    className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  >
                    {TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.replaceAll("_", " ").toLowerCase()}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs">
                  <span className="mb-1 block font-medium text-slate-600">From</span>
                  <input
                    type="date"
                    required
                    value={form.from_date}
                    onChange={(e) => setForm({ ...form, from_date: e.target.value })}
                    className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="text-xs">
                  <span className="mb-1 block font-medium text-slate-600">To</span>
                  <input
                    type="date"
                    required
                    value={form.to_date}
                    onChange={(e) => setForm({ ...form, to_date: e.target.value })}
                    className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </label>
              </div>
              <textarea
                rows={2}
                required
                minLength={5}
                placeholder="Reason"
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={form.guardian_consent}
                  onChange={(e) => setForm({ ...form, guardian_consent: e.target.checked })}
                />
                Guardian has consented
              </label>
              {error && <ErrorNote message={error} />}
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Submitting…" : "Request leave"}
              </Button>
            </form>
          </Card>
        </div>
      )}

      <Card title={isStaff ? `Leave requests (${data?.total ?? 0})` : "Your requests"}>
        {data?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {data.items.map((l) => (
              <li key={l.id} className="flex items-start justify-between gap-4 py-3">
                <div>
                  <p className="text-sm text-slate-800">
                    {l.leave_type.replaceAll("_", " ").toLowerCase()} · {l.from_date} → {l.to_date}
                  </p>
                  <p className="text-xs text-slate-500">{l.reason}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge value={l.status} />
                  {isStaff && l.status === "PENDING" && (
                    <>
                      <Button
                        variant="ghost"
                        onClick={() => decide.mutate({ id: l.id, status: "APPROVED" })}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => decide.mutate({ id: l.id, status: "REJECTED" })}
                      >
                        Reject
                      </Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No leave requests.</p>
        )}
      </Card>
    </Shell>
  );
}
