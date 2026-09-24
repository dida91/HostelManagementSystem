"use client";

import { BookOpenText, CircleAlert, FileText, Send, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Avatar, Button, PageHeader, Segmented, Skeleton, StatusPill, Tag } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import type { AssistantReply, RagReply } from "@/lib/api/types";
import { isStaff } from "@/lib/permissions";
import { useAsk, useAskDocuments, useMe } from "@/lib/queries";

type Mode = "records" | "rules";

interface Turn {
  id: number;
  mode: Mode;
  question: string;
  reply?: AssistantReply;
  rag?: RagReply;
  error?: unknown;
}

const LOOKUPS: Record<string, string> = {
  get_student_profile: "Your profile",
  get_room_assignment: "Your room",
  get_fee_balance: "Your fees",
  get_leave_requests: "Your leave",
  get_complaint_status: "Your complaints",
  get_mess_information: "Mess menu",
  search_announcements: "Notices",
  get_occupancy_summary: "Occupancy",
  search_hostel_documents: "Hostel documents",
};

const SUGGESTIONS: Record<Mode, { resident: string[]; office: string[] }> = {
  records: {
    resident: ["How much do I owe the hostel?", "Is my leave approved yet?", "What's for dinner today?"],
    office: ["How many beds are free right now?", "What's for dinner today?", "Are there any notices this week?"],
  },
  rules: {
    resident: ["What time must I be back at night?", "Can visitors come to my room?", "What happens if I pay fees late?"],
    office: ["What does the fee policy say about late payment?", "What are the visiting hours?", "What is the leave policy?"],
  },
};

function explain(error: unknown): string {
  if (error instanceof ApiError && error.status === 503) {
    return "The assistant is unavailable right now. Everything else in the portal still works.";
  }
  if (error instanceof ApiError && error.status === 429) {
    return "That's a lot of questions in a short time. Wait a minute and ask again.";
  }
  return error instanceof ApiError ? error.message : "That question didn't go through. Try again.";
}

function Answer({ turn }: { turn: Turn }) {
  if (turn.error) {
    return (
      <p className="flex items-start gap-2 text-body text-laligurans-300">
        <CircleAlert aria-hidden className="mt-1 h-4 w-4 shrink-0" />
        {explain(turn.error)}
      </p>
    );
  }
  if (turn.reply) {
    const lookups = Array.from(new Set(turn.reply.tool_calls.map((c) => LOOKUPS[String(c.name)] ?? String(c.name))));
    return (
      <div>
        <p className="whitespace-pre-wrap text-body text-snow">{turn.reply.text}</p>
        {lookups.length > 0 && (
          <p className="mt-3 flex flex-wrap items-center gap-2 text-small text-stone">
            Checked
            {lookups.map((l) => (
              <Tag key={l}>{l}</Tag>
            ))}
          </p>
        )}
      </div>
    );
  }
  if (turn.rag) {
    return (
      <div>
        <StatusPill tone={turn.rag.grounded ? "success" : "neutral"} className="mb-3">
          {turn.rag.grounded ? "From the hostel's documents" : "Not found in the documents"}
        </StatusPill>
        <p className="whitespace-pre-wrap text-body text-snow">{turn.rag.answer}</p>
        {turn.rag.citations.length > 0 && (
          <ul className="mt-4 space-y-1.5 border-t border-hairline pt-3">
            {turn.rag.citations.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-small text-mist">
                <FileText aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-stone" />
                <span>
                  {String(c.document_title ?? "Document")}
                  {c.page_number ? `, page ${c.page_number}` : ""}
                  {c.section_path ? `, ${c.section_path}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  return (
    <div className="space-y-2" aria-label="Thinking">
      <Skeleton className="w-11/12" />
      <Skeleton className="w-3/4" />
    </div>
  );
}

export function AssistantView() {
  const { data: me } = useMe();
  const [mode, setMode] = useState<Mode>("records");
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const ask = useAsk();
  const askDocs = useAskDocuments();
  const end = useRef<HTMLDivElement>(null);
  const busy = ask.isPending || askDocs.isPending;

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const send = (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    const id = Date.now();
    const turnMode = mode;
    setTurns((t) => [...t, { id, mode: turnMode, question: q }]);
    setDraft("");
    const settle = (patch: Partial<Turn>) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, ...patch } : x)));
    if (turnMode === "records") {
      ask.mutate(q, { onSuccess: (reply) => settle({ reply }), onError: (error) => settle({ error }) });
    } else {
      askDocs.mutate(q, { onSuccess: (rag) => settle({ rag }), onError: (error) => settle({ error }) });
    }
  };

  const who = isStaff(me?.role) ? "office" : "resident";
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Assistant"
        description="Answers come from your live records and the hostel's own documents. It doesn't remember earlier questions, so include the details each time."
      />
      <Segmented
        className="mb-6"
        label="What to ask about"
        value={mode}
        onChange={setMode}
        options={[
          { value: "records", label: who === "resident" ? "Your records" : "Hostel records" },
          { value: "rules", label: "Rules and policies" },
        ]}
      />

      <div className="space-y-6">
        {turns.length === 0 && (
          <div className="panel p-4 sm:p-6">
            <p className="flex items-center gap-2 text-ui text-mist">
              {mode === "records" ? <UserRound aria-hidden className="h-4 w-4" /> : <BookOpenText aria-hidden className="h-4 w-4" />}
              {mode === "records"
                ? "Ask about fees, leave, complaints, your room or the menu."
                : "Ask about hostel rules and policies. Answers cite the document they came from."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {SUGGESTIONS[mode][who].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-line px-3.5 py-1.5 text-ui text-snow transition-colors hover:border-marigold/60 hover:bg-lake-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t) => (
          <div key={t.id} className="space-y-3">
            <div className="flex items-start justify-end gap-3">
              <p className="max-w-[80%] rounded-panel rounded-tr-md bg-lake-700 px-4 py-2.5 text-body text-snow">{t.question}</p>
              {me && <Avatar name={me.full_name} size="sm" />}
            </div>
            <div className="panel max-w-[92%] p-5" aria-live="polite">
              <p className="mb-2 text-small text-stone">{t.mode === "records" ? "From the records" : "From the documents"}</p>
              <Answer turn={t} />
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>

      <form
        className="glass sticky bottom-4 mt-8 flex items-end gap-3 rounded-overlay p-3 shadow-overlay"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <label htmlFor="assistant-question" className="sr-only">
          Your question
        </label>
        <textarea
          id="assistant-question"
          rows={1}
          maxLength={2000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
          placeholder={mode === "records" ? "Ask about your fees, leave, room…" : "Ask about a rule or policy…"}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-body text-snow outline-none placeholder:text-stone"
        />
        <Button type="submit" variant="primary" icon={Send} loading={busy} disabled={!draft.trim()}>
          Ask
        </Button>
      </form>
    </div>
  );
}
