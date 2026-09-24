import { useQueryClient } from "@tanstack/react-query";

/**
 * Invalidate every query whose key starts with one of these roots.
 *
 * Mutations call this from onSuccess and must not wait for it. If they did,
 * TanStack Query would hold back the caller's own mutate() callbacks until the
 * refetch landed, and that fresh data can re-key or unmount the component that
 * fired the mutation first; its callbacks (a toast, closing a modal) are then
 * silently dropped.
 */
export function useInvalidate(): (...roots: string[]) => void {
  const qc = useQueryClient();
  return (...roots) => {
    for (const root of roots) void qc.invalidateQueries({ queryKey: [root] });
  };
}
