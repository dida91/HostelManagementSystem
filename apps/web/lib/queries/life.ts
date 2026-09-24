/** Mess, notices and notifications: the daily-life surfaces. */
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MessFeedbackCreate, NoticeCreate, NoticeUpdate } from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useMenu() {
  return useQuery({ queryKey: ["menu"], queryFn: api.mess.menu, staleTime: 5 * 60_000 });
}

export function useSetMenu() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (v: { day: number; meal: string; items: string; servingTime: string | null }) =>
      api.mess.setMenu(v.day, v.meal, v.items, v.servingTime),
    onSuccess: () => refresh("menu"),
  });
}

export function useRemoveMenu() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ day, meal }: { day: number; meal: string }) => api.mess.removeMenu(day, meal),
    onSuccess: () => refresh("menu"),
  });
}

export function useFeedback(params: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["feedback", params],
    queryFn: () => api.mess.feedback(params),
    placeholderData: keepPreviousData,
  });
}

export function useSubmitFeedback() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: MessFeedbackCreate) => api.mess.submitFeedback(body),
    onSuccess: () => refresh("feedback"),
  });
}

export function useNotices(includeExpired = false) {
  return useQuery({
    queryKey: ["notices", includeExpired],
    queryFn: () => api.notices.list(includeExpired),
  });
}

export function useCreateNotice() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: NoticeCreate) => api.notices.create(body),
    onSuccess: () => refresh("notices", "notifications"),
  });
}

export function useUpdateNotice() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: NoticeUpdate }) => api.notices.update(id, body),
    onSuccess: () => refresh("notices", "notifications"),
  });
}

export function useDeleteNotice() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.notices.remove(id),
    onSuccess: () => refresh("notices"),
  });
}

export function useNotifications(params: { unread_only?: boolean; limit?: number; offset?: number }, poll = false) {
  return useQuery({
    queryKey: ["notifications", params],
    queryFn: () => api.notifications.list(params),
    placeholderData: keepPreviousData,
    refetchInterval: poll ? 60_000 : false,
    refetchIntervalInBackground: false,
  });
}

export function useMarkRead() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.notifications.read(id),
    onSuccess: () => refresh("notifications"),
  });
}

export function useMarkAllRead() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: api.notifications.readAll,
    onSuccess: () => refresh("notifications"),
  });
}

export function useDeliveries(params: { status?: string; limit?: number; offset?: number }, enabled = true) {
  return useQuery({
    queryKey: ["deliveries", params],
    queryFn: () => api.notifications.deliveries(params),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useRetryFailed() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: api.notifications.retryFailed,
    onSuccess: () => refresh("deliveries"),
  });
}
