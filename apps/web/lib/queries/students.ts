import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { StudentCreate, StudentDeactivate, StudentUpdate } from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useStudents(params: { status?: string; q?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["students", params],
    queryFn: () => api.students.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useStudent(id: string | null | undefined) {
  return useQuery({
    queryKey: ["student", id],
    queryFn: () => api.students.get(id as string),
    enabled: !!id,
  });
}

const AFFECTED = ["students", "student", "rooms", "room", "blocks", "analytics"];

export function useCreateStudent() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: StudentCreate) => api.students.create(body),
    onSuccess: () => refresh(...AFFECTED),
  });
}

export function useUpdateStudent(id: string) {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: StudentUpdate) => api.students.update(id, body),
    onSuccess: () => refresh(...AFFECTED),
  });
}

export function useDeactivateStudent(id: string) {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: StudentDeactivate) => api.students.deactivate(id, body),
    onSuccess: () => refresh(...AFFECTED),
  });
}

export function useReactivateStudent(id: string) {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: () => api.students.reactivate(id),
    onSuccess: () => refresh(...AFFECTED),
  });
}

export function useResetPassword(id: string) {
  return useMutation({ mutationFn: (password: string) => api.students.resetPassword(id, password) });
}
