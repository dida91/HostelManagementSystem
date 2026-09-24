/**
 * Room colours for the block model and its legend. Kept free of three.js so
 * pages can import it without pulling the 3D bundle.
 *
 * Occupancy is a magnitude (one hue, brighter = fuller); maintenance and
 * closed are states, so they take state colours instead.
 */
export const ROOM_STATES = [
  { key: "vacant", label: "Empty", color: "#4a7d8a" },
  { key: "partial", label: "Partly filled", color: "#5a97e8" },
  { key: "full", label: "Full", color: "#b4d2f6" },
  { key: "maintenance", label: "Maintenance", color: "#c9962f" },
  { key: "closed", label: "Closed", color: "#1b3a42" },
] as const;

export type RoomState = (typeof ROOM_STATES)[number];

export function roomState(r: { status: string; beds: number; occupied: number }): RoomState {
  if (r.status === "CLOSED") return ROOM_STATES[4];
  if (r.status === "MAINTENANCE") return ROOM_STATES[3];
  if (r.occupied <= 0) return ROOM_STATES[0];
  if (r.occupied >= r.beds) return ROOM_STATES[2];
  return ROOM_STATES[1];
}
