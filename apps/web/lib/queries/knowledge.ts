/** Documents, assistant and analytics. */
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

import { useInvalidate } from "./shared";

export function useDocuments(params: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["documents", params],
    queryFn: () => api.documents.list(params),
    placeholderData: keepPreviousData,
    // Indexing runs in the background; poll while something is still processing.
    refetchInterval: (query) =>
      query.state.data?.items.some((d) => d.status === "UPLOADED" || d.status === "PROCESSING")
        ? 5_000
        : false,
  });
}

export function useUploadDocument() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (form: FormData) => api.documents.upload(form),
    onSuccess: () => refresh("documents"),
  });
}

export function useReindexDocument() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.documents.reindex(id),
    onSuccess: () => refresh("documents"),
  });
}

export function useDeleteDocument() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.documents.remove(id),
    onSuccess: () => refresh("documents"),
  });
}

export function useAsk() {
  return useMutation({ mutationFn: (message: string) => api.assistant.ask(message) });
}

export function useAskDocuments() {
  return useMutation({ mutationFn: (question: string) => api.assistant.askDocuments(question) });
}

export function useAnalytics(days = 30, enabled = true) {
  return useQuery({
    queryKey: ["analytics", days],
    queryFn: () => api.analytics.overview(days),
    enabled,
  });
}

export function useInsights() {
  return useMutation({ mutationFn: (days: number) => api.analytics.insights(days) });
}
