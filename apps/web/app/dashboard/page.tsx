"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge, Card } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  const { data: complaints } = useQuery({
    queryKey: ["complaints"],
    queryFn: api.listComplaints,
  });

  return (
    <Shell>
      <h1 className="mb-6 text-xl font-semibold text-slate-800">
        Welcome{me ? `, ${me.full_name.split(" ")[0]}` : ""}
      </h1>

      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Your complaints">
          {complaints?.items.length ? (
            <ul className="space-y-3">
              {complaints.items.slice(0, 5).map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-3">
                  <Link
                    href={`/complaints`}
                    className="line-clamp-2 text-sm text-slate-700 hover:underline"
                  >
                    {c.summary ?? c.raw_text}
                  </Link>
                  <Badge value={c.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No complaints filed.</p>
          )}
        </Card>

        <Card title="Quick links">
          <ul className="space-y-2 text-sm">
            <li>
              <Link href="/complaints" className="text-brand-700 hover:underline">
                File a complaint
              </Link>
            </li>
            <li>
              <Link href="/assistant" className="text-brand-700 hover:underline">
                Ask the hostel assistant
              </Link>
            </li>
          </ul>
        </Card>
      </div>
    </Shell>
  );
}
