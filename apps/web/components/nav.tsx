"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, type Me } from "@/lib/api";

export function Nav({ me }: { me: Me }) {
  const router = useRouter();
  const isStaff = me.role !== "STUDENT";

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/dashboard" className="text-sm font-semibold text-brand-700">
          Kutumba Hostel
        </Link>
        <Link href="/complaints" className="text-sm text-slate-600 hover:text-slate-900">
          Complaints
        </Link>
        <Link href="/assistant" className="text-sm text-slate-600 hover:text-slate-900">
          Assistant
        </Link>
        {isStaff && (
          <Link href="/admin/complaints" className="text-sm text-slate-600 hover:text-slate-900">
            Triage
          </Link>
        )}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {me.full_name} · {me.role.toLowerCase().replace("_", " ")}
          </span>
          <button
            onClick={async () => {
              await api.logout();
              router.push("/login");
            }}
            className="text-sm text-slate-500 underline hover:text-slate-800"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
