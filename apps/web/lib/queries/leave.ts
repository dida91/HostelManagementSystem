import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { LeaveCreate } from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useLeave(params: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["leave", params],
    queryFn: () => api.leave.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useRequestLeave() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: LeaveCreate) => api.leave.create(body),
    onSuccess: () => refresh("leave"),
  });
}

export function useDecideLeave() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: string; note?: string }) =>
      api.leave.decide(id, { status: status as "APPROVED", decision_note: note || null }),
    onSuccess: () => refresh("leave"),
  });
}
