"use client";

import { Building2, Ellipsis, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Guard } from "@/components/shell/guard";
import { BlockStage } from "@/components/three/block-stage";
import { ROOM_STATES, roomState } from "@/components/three/room-states";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  IconButton,
  Menu,
  PageHeader,
  Panel,
  Skeleton,
} from "@/components/ui";
import type { Block, Room } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { label } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useBlocks, useDeleteBlock, useMe, useRooms } from "@/lib/queries";
import { toast } from "@/lib/store";

import { BlockModal, RoomModal } from "./modals";
import { RoomDrawer } from "./room-drawer";

function RoomTile({ room, selected, onOpen }: { room: Room; selected: boolean; onOpen: () => void }) {
  const state = roomState({ status: room.status, beds: room.bed_count, occupied: room.occupied });
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Room ${room.room_number}, ${room.occupied} of ${room.bed_count} beds filled, ${state.label}`}
      className={cn(
        "group relative overflow-hidden rounded-panel border bg-lake-900/70 p-4 text-left transition duration-quick",
        "hover:-translate-y-0.5 hover:border-line-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60",
        selected ? "border-marigold/70" : "border-hairline",
      )}
    >
      <span aria-hidden className="absolute inset-x-0 top-0 h-[3px]" style={{ background: state.color }} />
      <span className="flex items-baseline justify-between gap-2">
        <span className="t-sub text-snow">{room.room_number}</span>
        <span className="text-small text-stone">Floor {room.floor}</span>
      </span>
      <span className="mt-1 block text-small text-mist">{label(room.room_type)}</span>
      <span className="mt-3 flex gap-1" aria-hidden>
        {Array.from({ length: room.bed_count }, (_, i) => (
          <span
            key={i}
            className={cn("h-1.5 flex-1 rounded-full", i < room.occupied ? "bg-glacier" : "bg-lake-700")}
          />
        ))}
      </span>
      <span className="mt-2 block text-small text-stone">
        {room.occupied}/{room.bed_count} filled
        {room.status !== "AVAILABLE" && room.status !== "FULL" ? `, ${label(room.status).toLowerCase()}` : ""}
      </span>
    </button>
  );
}

function Rooms() {
  const { data: me } = useMe();
  const blocks = useBlocks();
  const rooms = useRooms();
  const removeBlock = useDeleteBlock();
  const [selected, setSelected] = useState<string | null>(null);
  const [blockModal, setBlockModal] = useState<Block | "new" | null>(null);
  const [roomModal, setRoomModal] = useState<{ blockId?: string } | null>(null);
  const [deletingBlock, setDeletingBlock] = useState<Block | null>(null);
  const manage = can(me?.role, "manageRooms");

  const byBlock = useMemo(() => {
    const map = new Map<string, Room[]>();
    for (const r of rooms.data ?? []) map.set(r.block_id, [...(map.get(r.block_id) ?? []), r]);
    return map;
  }, [rooms.data]);
  const totals = useMemo(() => {
    const list = rooms.data ?? [];
    return {
      rooms: list.length,
      beds: list.reduce((s, r) => s + r.bed_count, 0),
      occupied: list.reduce((s, r) => s + r.occupied, 0),
    };
  }, [rooms.data]);
  const model = useMemo(
    () => ({
      blocks: (blocks.data ?? []).map((b) => ({ id: b.id, name: b.name })),
      rooms: (rooms.data ?? []).map((r) => ({
        id: r.id,
        blockId: r.block_id,
        floor: r.floor,
        number: r.room_number,
        beds: r.bed_count,
        occupied: r.occupied,
        status: r.status,
      })),
    }),
    [blocks.data, rooms.data],
  );

  if (!me) return null;
  const loading = blocks.isPending || rooms.isPending;
  const error = blocks.error ?? rooms.error;

  return (
    <>
      <PageHeader
        title="Rooms"
        description={
          loading
            ? "Every block, room and bed."
            : `${totals.occupied} of ${totals.beds} beds filled across ${totals.rooms} rooms. Select a room to allocate or vacate beds.`
        }
        actions={
          manage && (
            <>
              <Button icon={Building2} onClick={() => setBlockModal("new")}>
                Add block
              </Button>
              <Button variant="primary" icon={Plus} disabled={!blocks.data?.length} onClick={() => setRoomModal({})}>
                Add room
              </Button>
            </>
          )
        }
      />

      {error ? (
        <div className="panel">
          <ErrorState error={error} onRetry={() => (blocks.refetch(), rooms.refetch())} />
        </div>
      ) : loading ? (
        <Skeleton className="h-[380px] w-full rounded-stage" />
      ) : model.rooms.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={Building2}
            title={blocks.data?.length ? "No rooms yet" : "Set up the hostel"}
            description={blocks.data?.length ? "Add rooms to a block and their beds are created with them." : "Start with a block, then add its rooms."}
            action={
              manage && (
                <Button variant="primary" onClick={() => (blocks.data?.length ? setRoomModal({}) : setBlockModal("new"))}>
                  {blocks.data?.length ? "Add room" : "Add block"}
                </Button>
              )
            }
          />
        </div>
      ) : (
        <>
          <BlockStage
            blocks={model.blocks}
            rooms={model.rooms}
            selectedId={selected}
            onSelect={setSelected}
            className="h-[340px] sm:h-[420px]"
          />
          <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2" aria-label="Room colours">
            {ROOM_STATES.map((s) => (
              <li key={s.key} className="flex items-center gap-2 text-small text-mist">
                <span aria-hidden className="h-2.5 w-2.5 rounded-[3px]" style={{ background: s.color }} />
                {s.label}
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="mt-8 space-y-5">
        {(blocks.data ?? []).map((b) => {
          const list = (byBlock.get(b.id) ?? []).sort((x, y) => x.floor - y.floor || x.room_number.localeCompare(y.room_number, undefined, { numeric: true }));
          const beds = list.reduce((s, r) => s + r.bed_count, 0);
          const filled = list.reduce((s, r) => s + r.occupied, 0);
          return (
            <Panel
              key={b.id}
              title={b.name}
              description={`${b.floors} ${b.floors === 1 ? "floor" : "floors"}, ${list.length} ${list.length === 1 ? "room" : "rooms"}, ${filled} of ${beds} beds filled`}
              actions={
                manage && (
                  <Menu
                    label={`${b.name} actions`}
                    items={[
                      { label: "Add a room here", icon: Plus, onSelect: () => setRoomModal({ blockId: b.id }) },
                      { label: "Edit block", icon: Pencil, onSelect: () => setBlockModal(b) },
                      { label: "Delete block", icon: Trash2, tone: "danger", onSelect: () => setDeletingBlock(b) },
                    ]}
                    trigger={(props) => <IconButton {...props} icon={Ellipsis} label={`${b.name} actions`} size="sm" />}
                  />
                )
              }
            >
              {list.length === 0 ? (
                <p className="text-ui text-stone">No rooms in this block yet.</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
                  {list.map((r) => (
                    <RoomTile key={r.id} room={r} selected={selected === r.id} onOpen={() => setSelected(r.id)} />
                  ))}
                </div>
              )}
            </Panel>
          );
        })}
      </div>

      <RoomDrawer id={selected} me={me} blocks={blocks.data ?? []} onClose={() => setSelected(null)} />
      {blockModal && <BlockModal block={blockModal === "new" ? null : blockModal} onClose={() => setBlockModal(null)} />}
      {roomModal && blocks.data && (
        <RoomModal blocks={blocks.data} room={null} defaultBlockId={roomModal.blockId} onClose={() => setRoomModal(null)} />
      )}
      <ConfirmDialog
        open={!!deletingBlock}
        onClose={() => setDeletingBlock(null)}
        title={`Delete ${deletingBlock?.name ?? "block"}?`}
        confirmLabel="Delete block"
        tone="danger"
        loading={removeBlock.isPending}
        onConfirm={() =>
          deletingBlock &&
          removeBlock.mutate(deletingBlock.id, {
            onSuccess: () => {
              toast.success("Block deleted");
              setDeletingBlock(null);
            },
            onError: (e) => {
              toast.error("Block not deleted", e.message);
              setDeletingBlock(null);
            },
          })
        }
      >
        <p>Only a block with no rooms can be deleted.</p>
      </ConfirmDialog>
    </>
  );
}

export function RoomsView() {
  return (
    <Guard capability="viewRooms">
      <Rooms />
    </Guard>
  );
}
