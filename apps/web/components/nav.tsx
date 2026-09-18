"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { clsx } from "@/lib/clsx";
import { api, type Me } from "@/lib/api";

const STUDENT_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/complaints", label: "Complaints" },
  { href: "/leave", label: "Leave" },
  { href: "/fees", label: "Fees" },
  { href: "/mess", label: "Mess" },
  { href: "/assistant", label: "Assistant" },
];

const STAFF_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/admin/complaints", label: "Triage" },
  { href: "/leave", label: "Leave" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/documents", label: "Documents" },
  { href: "/mess", label: "Mess" },
  { href: "/assistant", label: "Assistant" },
];

export function Nav({ me }: { me: Me }) {
  const router = useRouter();
  const pathname = usePathname();
  const links = me.role === "STUDENT" ? STUDENT_LINKS : STAFF_LINKS;

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <span className="text-sm font-semibold text-brand-700">Kutumba Hostel</span>
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={clsx(
              "text-sm transition",
              pathname === l.href
                ? "font-medium text-brand-700"
                : "text-slate-600 hover:text-slate-900",
            )}
          >
            {l.label}
          </Link>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {me.full_name} · {me.role.toLowerCase().replaceAll("_", " ")}
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
