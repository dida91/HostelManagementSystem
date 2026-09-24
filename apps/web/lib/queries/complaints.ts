import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ComplaintOverride } from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useComplaints(params: { status?: string[]; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["complaints", params],
    queryFn: () => api.complaints.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useComplaint(id: string | null | undefined) {
  return useQuery({
    queryKey: ["complaint", id],
    queryFn: () => api.complaints.get(id as string),
    enabled: !!id,
  });
}

export function useFileComplaint() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (text: string) => api.complaints.create(text),
    onSuccess: () => refresh("complaints"),
  });
}

export function useOverrideComplaint(id: string) {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: ComplaintOverride) => api.complaints.override(id, body),
    onSuccess: () => refresh("complaints", "complaint", "analytics"),
  });
}
