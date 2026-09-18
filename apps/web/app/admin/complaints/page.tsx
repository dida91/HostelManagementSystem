"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError, type ComplaintDetail } from "@/lib/api";

const CATEGORIES = ["WATER", "ELECTRICITY", "INTERNET", "CLEANLINESS", "FOOD", "MAINTENANCE", "SECURITY", "NOISE", "HARASSMENT", "STAFF_BEHAVIOUR", "OTHER"];
const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];
const DEPARTMENTS = ["MAINTENANCE", "HOUSEKEEPING", "MESS", "SECURITY", "IT", "ADMINISTRATION", "WARDEN_OFFICE"];
const STATUSES = ["SUBMITTED", "TRIAGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"];

function Select({
  label, value, options, onChange,
}: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="block text-xs">
      <span className="mb-1 block font-medium text-slate-600">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o} value={o}>{o.replaceAll("_", " ").toLowerCase()}</option>
        ))}
      </select>
    </label>
  );
}

function TriageRow({ id }: { id: string }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const { data } = useQuery<ComplaintDetail>({
    queryKey: ["complaint", id],
    queryFn: () => api.getComplaint(id),
  });
  const [draft, setDraft] = useState<Record<string, string>>({});

  const save = useMutation({
    mutationFn: () => api.overrideComplaint(id, draft),
    onSuccess: () => {
      setDraft({});
      setError(null);
      qc.invalidateQueries({ queryKey: ["complaint", id] });
      qc.invalidateQueries({ queryKey: ["complaints"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save."),
  });

  if (!data) return <p className="py-3 text-sm text-slate-400">Loading…</p>;
  const ai = data.ai_analysis;
  const val = (k: keyof ComplaintDetail) => draft[k] ?? (data[k] as string | null) ?? "";

  return (
    <div className="space-y-3 py-4">
      <p className="text-sm text-slate-800">{data.raw_text}</p>

      {ai ? (
        <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
          <p className="mb-1 font-medium text-slate-700">
            AI suggestion · {ai.model} · {ai.prompt_version}
            {ai.confidence !== null && ` · confidence ${(ai.confidence * 100).toFixed(0)}%`}
          </p>
          <p>
            {ai.category} / {ai.priority} / {ai.suggested_department} ·{" "}
            sentiment {ai.sentiment} · {ai.location ?? "no location stated"}
          </p>
          {ai.summary && <p className="mt-1 italic">{ai.summary}</p>}
        </div>
      ) : (
        <p className="text-xs text-slate-400">No AI analysis (queued, failed, or AI disabled).</p>
      )}

      <div className="grid gap-3 sm:grid-cols-4">
        <Select label="Category" value={val("category")} options={CATEGORIES}
          onChange={(v) => setDraft({ ...draft, category: v })} />
        <Select label="Priority" value={val("priority")} options={PRIORITIES}
          onChange={(v) => setDraft({ ...draft, priority: v })} />
        <Select label="Department" value={val("department")} options={DEPARTMENTS}
          onChange={(v) => setDraft({ ...draft, department: v })} />
        <Select label="Status" value={val("status")} options={STATUSES}
          onChange={(v) => setDraft({ ...draft, status: v })} />
      </div>

      {error && <ErrorNote message={error} />}

      <div className="flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={!Object.keys(draft).length || save.isPending}>
          {save.isPending ? "Saving…" : "Save override"}
        </Button>
        {data.overridden_fields?.length ? (
          <span className="text-xs text-slate-500">
            overridden by staff: {data.overridden_fields.join(", ")}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default function AdminComplaintsPage() {
  const { data } = useQuery({ queryKey: ["complaints"], queryFn: api.listComplaints });

  return (
    <Shell>
      <h1 className="mb-2 text-xl font-semibold text-slate-800">Complaint triage</h1>
      <p className="mb-6 text-sm text-slate-500">
        AI triage is advisory. Any field you change is recorded as a staff override and audited.
      </p>

      <Card title={`Open complaints (${data?.total ?? 0})`}>
        {data?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {data.items.map((c) => (
              <li key={c.id}>
                <div className="flex items-center gap-2 pt-3">
                  <Badge value={c.priority} />
                  <Badge value={c.status} />
                  <span className="text-xs text-slate-400">
                    {new Date(c.created_at).toLocaleString()}
                  </span>
                </div>
                <TriageRow id={c.id} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">Nothing to triage.</p>
        )}
      </Card>
    </Shell>
  );
}
