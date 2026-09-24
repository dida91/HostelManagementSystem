import { useId } from "react";

/**
 * An id safe inside url(#…), unique per mounted SVG. Gradients must not share
 * ids: if the first copy sits in a hidden subtree (the sidebar on phones),
 * every other copy that points at it renders blank.
 */
export function useSvgId(prefix: string): string {
  return `${prefix}-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
}
