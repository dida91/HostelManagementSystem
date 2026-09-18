"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Nav } from "@/components/nav";
import { api } from "@/lib/api";

export function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: me, isLoading, isError } = useQuery({ queryKey: ["me"], queryFn: api.me });

  useEffect(() => {
    if (isError) router.push("/login");
  }, [isError, router]);

  if (isLoading) return <p className="p-8 text-sm text-slate-500">Loading…</p>;
  if (!me) return null;

  return (
    <>
      <Nav me={me} />
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </>
  );
}
