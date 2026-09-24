"use client";

import { BedDouble, DoorOpen, Ellipsis, Pencil, Trash2, UserPlus, Wrench } from "lucide-react";
import { useState } from "react";

import {
  Button,
  ConfirmDialog,
  Details,
  Drawer,
  EnumPill,
  ErrorState,
  IconButton,
  Menu,
  type MenuItem,
  SkeletonLines,
} from "@/components/ui";
import type { Bed, Block, Me } from "@/lib/api/types";
import { formatDate, npr } from "@/lib/format";
import { label } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useDeleteRoom, useRoom, useSetBedStatus, useVacate } from "@/lib/queries";
import { toast } from "@/lib/store";

import { AllocateModal, RoomModal } from "./modals";

export function RoomDrawer({
  id,
  me,
  blocks,
  onClose,
}: {
  id: string | null;
  me: Me;
  blocks: Block[];
  onClose: () => void;
}) {
  const room = useRoom(id);
  const vacate = useVacate();
  const setBed = useSetBedStatus();
  const remove = useDeleteRoom();
  const [allocating, setAllocating] = useState<Bed | null>(null);
  const [vacating, setVacating] = useState<Bed | null>(null);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const manage = can(me.role, "manageRooms");
  const allocate = can(me.role, "allocateBeds");
  const r = room.data;
  const roomLabel = r ? `${r.block_name ?? "Block"}, room ${r.room_number}` : "";
  const open = r ? !["MAINTENANCE", "CLOSED"].includes(r.status) : false;

  const bedMenu = (bed: Bed): MenuItem[] =>
    (["VACANT", "RESERVED", "OUT_OF_SERVICE"] as const)
      .filter((s) => s !== bed.status)
      .map((s) => ({
        label: s === "VACANT" ? "Mark available" : s === "RESERVED" ? "Reserve bed" : "Take out of service",
        icon: s === "OUT_OF_SERVICE" ? Wrench : BedDouble,
        onSelect: () =>
          setBed.mutate(
            { bedId: bed.id, status: s },
            { onSuccess: () => toast.success(`Bed ${bed.bed_label}: ${label(s).toLowerCase()}`), onError: (e) => toast.error("Bed not changed", e.message) },
          ),
      }));

  return (
    <>
      <Drawer
        open={!!id && !editing && !deleting && !allocating && !vacating}
        onClose={onClose}
        title={r ? `Room ${r.room_number}` : "Room"}
        description={
          r && (
            <span className="flex flex-wrap items-center gap-2">
              {r.block_name}, floor {r.floor}
              <EnumPill domain="roomStatus" value={r.status} />
            </span>
          )
        }
        footer={
          manage && r ? (
            <>
              <Button variant="ghost" icon={Trash2} className="mr-auto" onClick={() => setDeleting(true)}>
                Delete room
              </Button>
              <Button icon={Pencil} onClick={() => setEditing(true)}>
                Edit room
              </Button>
            </>
          ) : undefined
        }
      >
        {room.isError ? (
          <ErrorState error={room.error} onRetry={() => room.refetch()} />
        ) : !r ? (
          <SkeletonLines lines={6} />
        ) : (
          <div className="space-y-7">
            <Details
              items={[
                ["Type", `${label(r.room_type)}, ${r.bed_count} ${r.bed_count === 1 ? "bed" : "beds"}`],
                ["Monthly rent", r.monthly_rate_npr != null ? npr(r.monthly_rate_npr, true) : "Not set"],
                ["Occupied", `${r.occupied} of ${r.bed_count}`],
              ]}
            />
            {!open && (
              <p className="rounded-control border border-marigold/30 bg-marigold/10 px-3 py-2.5 text-ui text-marigold-300">
                This room is {label(r.status).toLowerCase()}, so no one can be allocated here.
              </p>
            )}
            <section>
              <h3 className="t-sub mb-3">Beds</h3>
              <ul className="rows rounded-panel border border-hairline">
                {r.beds.map((bed) => (
                  <li key={bed.id} className="flex items-center gap-3 px-4 py-3.5">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-control bg-lake-800 t-sub text-snow">
                      {bed.bed_label}
                    </span>
                    <div className="min-w-0 flex-1">
                      {bed.occupant ? (
                        <>
                          <p className="truncate text-ui text-snow">{bed.occupant.full_name}</p>
                          <p className="text-small text-stone">
                            {bed.occupant.student_code}, since {formatDate(bed.occupant.from_date)}
                          </p>
                        </>
                      ) : (
                        <EnumPill domain="bedStatus" value={bed.status} />
                      )}
                    </div>
                    {bed.occupant && allocate && (
                      <Button size="sm" icon={DoorOpen} onClick={() => setVacating(bed)}>
                        Vacate
                      </Button>
                    )}
                    {!bed.occupant && allocate && open && bed.status !== "OUT_OF_SERVICE" && (
                      <Button size="sm" variant="primary" icon={UserPlus} onClick={() => setAllocating(bed)}>
                        Allocate
                      </Button>
                    )}
                    {!bed.occupant && manage && (
                      <Menu
                        label={`Bed ${bed.bed_label} actions`}
                        items={bedMenu(bed)}
                        trigger={(props) => <IconButton {...props} icon={Ellipsis} label={`Bed ${bed.bed_label} actions`} size="sm" />}
                      />
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </Drawer>

      {editing && r && <RoomModal blocks={blocks} room={r} onClose={() => setEditing(false)} />}
      {allocating && <AllocateModal bed={allocating} roomLabel={roomLabel} onClose={() => setAllocating(null)} />}
      <ConfirmDialog
        open={!!vacating}
        onClose={() => setVacating(null)}
        title={`Vacate bed ${vacating?.bed_label ?? ""}?`}
        confirmLabel="Vacate bed"
        loading={vacate.isPending}
        onConfirm={() =>
          vacating?.occupant &&
          vacate.mutate(vacating.occupant.assignment_id, {
            onSuccess: () => {
              toast.success("Bed vacated", `${vacating.occupant?.full_name} no longer has a bed.`);
              setVacating(null);
            },
            onError: (e) => toast.error("Bed not vacated", e.message),
          })
        }
      >
        <p>
          {vacating?.occupant?.full_name} moves out of {roomLabel} today. Their residency history is kept.
        </p>
      </ConfirmDialog>
      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        title={`Delete room ${r?.room_number ?? ""}?`}
        confirmLabel="Delete room"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() =>
          r &&
          remove.mutate(r.id, {
            onSuccess: () => {
              toast.success("Room deleted");
              setDeleting(false);
              onClose();
            },
            onError: (e) => {
              toast.error("Room not deleted", e.message);
              setDeleting(false);
            },
          })
        }
      >
        <p>Only rooms nobody has ever lived in can be deleted. Otherwise, set the room to closed.</p>
      </ConfirmDialog>
    </>
  );
}
