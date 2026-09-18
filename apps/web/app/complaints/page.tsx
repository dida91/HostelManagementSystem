"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";

export default function ComplaintsPage() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({ queryKey: ["complaints"], queryFn: api.listComplaints });

  const create = useMutation({
    mutationFn: () => api.createComplaint(text),
    onSuccess: () => {
      setText("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["complaints"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit."),
  });

  return (
    <Shell>
      <h1 className="mb-6 text-xl font-semibold text-slate-800">Complaints</h1>

      <div className="mb-6">
        <Card title="File a complaint">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
            className="space-y-3"
          >
            <label htmlFor="text" className="block text-sm text-slate-600">
              Describe the issue in your own words. You can write in English or Nepali.
            </label>
            <textarea
              id="text"
              rows={4}
              minLength={10}
              maxLength={4000}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            {error && <ErrorNote message={error} />}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={create.isPending || text.trim().length < 10}>
                {create.isPending ? "Submitting…" : "Submit"}
              </Button>
              <span className="text-xs text-slate-500">
                Staff review every complaint. AI triage is a suggestion only.
              </span>
            </div>
          </form>
        </Card>
      </div>

      <Card title={`Your complaints (${data?.total ?? 0})`}>
        {data?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {data.items.map((c) => (
              <li key={c.id} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm text-slate-700">{c.raw_text}</p>
                  <div className="flex shrink-0 gap-2">
                    <Badge value={c.priority} />
                    <Badge value={c.status} />
                  </div>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {new Date(c.created_at).toLocaleString()}
                  {c.category ? ` · ${c.category.toLowerCase()}` : ""}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">Nothing filed yet.</p>
        )}
      </Card>
    </Shell>
  );
}
