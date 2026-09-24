import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.auth.me, staleTime: 5 * 60_000 });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) =>
      api.auth.changePassword(current, next),
  });
}
