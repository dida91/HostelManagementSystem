"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MEALS = ["BREAKFAST", "LUNCH", "SNACKS", "DINNER"];

export default function MessPage() {
  const qc = useQueryClient();
  const { data: menu } = useQuery({ queryKey: ["menu"], queryFn: api.menu });
  const { data: feedback } = useQuery({ queryKey: ["feedback"], queryFn: api.listFeedback });
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    meal_date: new Date().toISOString().slice(0, 10),
    meal_type: "DINNER",
    rating: 4,
    comment: "",
  });

  const submit = useMutation({
    mutationFn: () => api.submitFeedback(form),
    onSuccess: () => {
      setForm({ ...form, comment: "" });
      setError(null);
      qc.invalidateQueries({ queryKey: ["feedback"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit."),
  });

  const today = new Date().getDay();
  const todayMenu = menu?.filter((m) => m.day_of_week === today) ?? [];

  return (
    <Shell>
      <h1 className="mb-6 text-xl font-semibold text-slate-800">Mess</h1>

      <div className="mb-6 grid gap-5 md:grid-cols-2">
        <Card title={`Today's menu — ${DAYS[today]}`}>
          {todayMenu.length ? (
            <ul className="space-y-2 text-sm">
              {todayMenu.map((m) => (
                <li key={m.meal_type} className="flex justify-between gap-4">
                  <span className="font-medium text-slate-700">
                    {m.meal_type.toLowerCase()}
                  </span>
                  <span className="text-right text-slate-600">
                    {m.items}
                    {m.serving_time && (
                      <span className="block text-xs text-slate-400">{m.serving_time}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No menu published for today.</p>
          )}
        </Card>

        <Card title="Rate a meal">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit.mutate();
            }}
            className="space-y-3"
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="text-xs">
                <span className="mb-1 block font-medium text-slate-600">Date</span>
                <input
                  type="date"
                  value={form.meal_date}
                  onChange={(e) => setForm({ ...form, meal_date: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs">
                <span className="mb-1 block font-medium text-slate-600">Meal</span>
                <select
                  value={form.meal_type}
                  onChange={(e) => setForm({ ...form, meal_type: e.target.value })}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                >
                  {MEALS.map((m) => (
                    <option key={m} value={m}>
                      {m.toLowerCase()}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                <span className="mb-1 block font-medium text-slate-600">Rating</span>
                <select
                  value={form.rating}
                  onChange={(e) => setForm({ ...form, rating: Number(e.target.value) })}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                >
                  {[1, 2, 3, 4, 5].map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <textarea
              rows={2}
              placeholder="Optional comment — English or Nepali"
              value={form.comment}
              onChange={(e) => setForm({ ...form, comment: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            {error && <ErrorNote message={error} />}
            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending ? "Submitting…" : "Submit feedback"}
            </Button>
          </form>
        </Card>
      </div>

      <Card title="Recent feedback">
        {feedback?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {feedback.items.map((f) => (
              <li key={f.id} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm text-slate-800">
                      {f.meal_type.toLowerCase()} · {f.meal_date} · {f.rating}/5
                    </p>
                    {f.comment && <p className="text-sm text-slate-600">{f.comment}</p>}
                  </div>
                  {f.analysis?.sentiment && <Badge value={f.analysis.sentiment} />}
                </div>
                {f.analysis?.issues?.length ? (
                  <p className="mt-1 text-xs text-slate-500">
                    AI-identified issues: {f.analysis.issues.join(", ")}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No feedback yet.</p>
        )}
      </Card>
    </Shell>
  );
}
