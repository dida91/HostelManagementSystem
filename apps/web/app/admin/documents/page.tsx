"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { ApiError, api } from "@/lib/api";

const DOC_TYPES = [
  "HOSTEL_RULES", "FEE_POLICY", "LEAVE_POLICY", "MESS_POLICY", "NOTICE", "FAQ", "OTHER",
];

export default function DocumentsPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      // Multipart must bypass the JSON client, but still goes through the BFF.
      const res = await fetch("/api/bff/documents", {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new ApiError(res.status, body.title ?? "error", body.detail ?? "Upload failed.");
      }
      e.currentTarget.reset();
      qc.invalidateQueries({ queryKey: ["documents"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  const reindex = useMutation({
    mutationFn: (id: string) => api.reindexDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <Shell>
      <h1 className="mb-2 text-xl font-semibold text-slate-800">Hostel documents</h1>
      <p className="mb-6 text-sm text-slate-500">
        Uploaded rules and policies are parsed, chunked and indexed so the assistant can answer
        from them with citations.
      </p>

      <div className="mb-6">
        <Card title="Upload a document">
          <form onSubmit={upload} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="text-xs sm:col-span-2">
                <span className="mb-1 block font-medium text-slate-600">Title</span>
                <input
                  name="title"
                  required
                  minLength={2}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                />
              </label>
              <label className="text-xs">
                <span className="mb-1 block font-medium text-slate-600">Type</span>
                <select
                  name="doc_type"
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                >
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t.replaceAll("_", " ").toLowerCase()}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <input
              type="file"
              name="file"
              required
              accept=".pdf,.txt,.md"
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-brand-600 file:px-3 file:py-2 file:text-sm file:text-white"
            />
            {error && <ErrorNote message={error} />}
            <Button type="submit" disabled={busy}>
              {busy ? "Uploading…" : "Upload and index"}
            </Button>
          </form>
        </Card>
      </div>

      <Card title={`Indexed documents (${data?.total ?? 0})`}>
        {data?.items.length ? (
          <ul className="divide-y divide-slate-100">
            {data.items.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{d.title}</p>
                  <p className="text-xs text-slate-500">
                    {d.filename} · {d.doc_type.replaceAll("_", " ").toLowerCase()}
                    {d.page_count ? ` · ${d.page_count} pages` : ""} · {d.chunk_count} chunks
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge value={d.status === "INDEXED" ? "RESOLVED" : d.status} />
                  <Button variant="ghost" onClick={() => reindex.mutate(d.id)}>
                    Reindex
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">
            No documents indexed. Until one is uploaded, the assistant cannot answer policy
            questions.
          </p>
        )}
      </Card>
    </Shell>
  );
}
