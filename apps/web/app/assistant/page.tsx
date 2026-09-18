"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError, type AssistantReply } from "@/lib/api";

export default function AssistantPage() {
  const [message, setMessage] = useState("");
  const [turns, setTurns] = useState<{ q: string; a: AssistantReply }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const ask = useMutation({
    mutationFn: (q: string) => api.ask(q),
    onSuccess: (a, q) => {
      setTurns((t) => [...t, { q, a }]);
      setMessage("");
      setError(null);
    },
    onError: (e) =>
      setError(
        e instanceof ApiError && e.status === 503
          ? "The assistant is unavailable right now. Everything else still works."
          : "Could not get an answer.",
      ),
  });

  return (
    <Shell>
      <h1 className="mb-2 text-xl font-semibold text-slate-800">Hostel assistant</h1>
      <p className="mb-6 text-sm text-slate-500">
        Ask about hostel rules, your room, fees or leave. Personal figures are read live from your
        records — the assistant never estimates them.
      </p>

      <div className="space-y-4">
        {turns.map((t, i) => (
          <Card key={i}>
            <p className="mb-2 text-sm font-medium text-slate-700">{t.q}</p>
            <p className="whitespace-pre-wrap text-sm text-slate-800">{t.a.text}</p>
            {t.a.tool_calls.length > 0 && (
              <p className="mt-3 text-xs text-slate-500">
                Checked:{" "}
                {t.a.tool_calls.map((c) => c.name.replaceAll("_", " ")).join(", ")}
              </p>
            )}
          </Card>
        ))}

        <Card>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (message.trim()) ask.mutate(message.trim());
            }}
            className="space-y-3"
          >
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What time is dinner? What is my outstanding fee?"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            {error && <ErrorNote message={error} />}
            <Button type="submit" disabled={ask.isPending || !message.trim()}>
              {ask.isPending ? "Thinking…" : "Ask"}
            </Button>
          </form>
        </Card>
      </div>
    </Shell>
  );
}
