"use client";

import { useState } from "react";

import { StudentPicker } from "@/components/domain/student-picker";
import { Button, Field, fieldErrors, FieldRow, FormError, Input, Modal, Select, Textarea } from "@/components/ui";
import type { Block, RoomDetail, Student } from "@/lib/api/types";
import { todayISO } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { useAllocate, useCreateBlock, useCreateRoom, useUpdateBlock, useUpdateRoom } from "@/lib/queries";
import { toast } from "@/lib/store";

const BEDS_FOR: Record<string, number> = { SINGLE: 1, DOUBLE: 2, TRIPLE: 3 };

export function BlockModal({ block, onClose }: { block: Block | null; onClose: () => void }) {
  const create = useCreateBlock();
  const update = useUpdateBlock();
  const mutation = block ? update : create;
  const [form, setForm] = useState({
    name: block?.name ?? "",
    floors: String(block?.floors ?? 3),
    description: block?.description ?? "",
  });
  const errors = fieldErrors(mutation.error);
  const floors = Number(form.floors);
  const valid = form.name.trim() && floors >= 1 && floors <= 50;
  const submit = () => {
    const body = { name: form.name.trim(), floors, description: form.description.trim() || null };
    const done = () => {
      toast.success(block ? "Block updated" : "Block added", body.name);
      onClose();
    };
    if (block) update.mutate({ id: block.id, body }, { onSuccess: done });
    else create.mutate(body, { onSuccess: done });
  };
  return (
    <Modal
      open
      onClose={onClose}
      busy={mutation.isPending}
      title={block ? `Edit ${block.name}` : "Add a block"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button variant="primary" loading={mutation.isPending} disabled={!valid} onClick={submit}>
            {block ? "Save block" : "Add block"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FieldRow>
          <Field label="Name" htmlFor="block-name" required error={errors.name}>
            <Input id="block-name" maxLength={80} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="B Block" />
          </Field>
          <Field label="Floors" htmlFor="block-floors" required help="Ground floor is floor 0." error={errors.floors}>
            <Input id="block-floors" type="number" min={1} max={50} value={form.floors} onChange={(e) => setForm({ ...form, floors: e.target.value })} />
          </Field>
        </FieldRow>
        <Field label="Description" htmlFor="block-description">
          <Textarea id="block-description" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <FormError error={mutation.error} />
      </div>
    </Modal>
  );
}

export function RoomModal({
  blocks,
  room,
  defaultBlockId,
  onClose,
}: {
  blocks: Block[];
  room: RoomDetail | null;
  defaultBlockId?: string;
  onClose: () => void;
}) {
  const create = useCreateRoom();
  const update = useUpdateRoom();
  const mutation = room ? update : create;
  const [form, setForm] = useState({
    block_id: room?.block_id ?? defaultBlockId ?? blocks[0]?.id ?? "",
    floor: String(room?.floor ?? 1),
    room_number: room?.room_number ?? "",
    room_type: String(room?.room_type ?? "DOUBLE"),
    capacity: String(room?.capacity ?? 2),
    monthly_rate_npr: room?.monthly_rate_npr != null ? String(room.monthly_rate_npr) : "",
    status: String(room?.status ?? "AVAILABLE"),
  });
  const errors = fieldErrors(mutation.error);
  const fixed = BEDS_FOR[form.room_type];
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const valid = form.block_id && form.room_number.trim() && Number(form.capacity) >= 1;

  const submit = () => {
    const body = {
      floor: Number(form.floor),
      room_number: form.room_number.trim(),
      room_type: form.room_type as "DOUBLE",
      capacity: fixed ?? Number(form.capacity),
      monthly_rate_npr: form.monthly_rate_npr === "" ? null : Number(form.monthly_rate_npr),
      status: form.status as "AVAILABLE",
    };
    const done = () => {
      toast.success(room ? "Room updated" : "Room added", `Room ${body.room_number}`);
      onClose();
    };
    if (room) update.mutate({ id: room.id, body }, { onSuccess: done });
    else create.mutate({ ...body, block_id: form.block_id }, { onSuccess: done });
  };

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      busy={mutation.isPending}
      title={room ? `Edit room ${room.room_number}` : "Add a room"}
      description={room ? "Changing the number of beds adds beds, or removes beds that were never used." : "Its beds (A, B, C…) are created with it."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button variant="primary" loading={mutation.isPending} disabled={!valid} onClick={submit}>
            {room ? "Save room" : "Add room"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FieldRow cols={3}>
          <Field label="Block" htmlFor="room-block" required>
            <Select id="room-block" value={form.block_id} disabled={!!room} onChange={(e) => set({ block_id: e.target.value })}>
              {blocks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Floor" htmlFor="room-floor" required error={errors.floor}>
            <Input id="room-floor" type="number" min={0} max={50} value={form.floor} onChange={(e) => set({ floor: e.target.value })} />
          </Field>
          <Field label="Room number" htmlFor="room-number" required error={errors.room_number}>
            <Input id="room-number" maxLength={20} value={form.room_number} onChange={(e) => set({ room_number: e.target.value })} placeholder="204" />
          </Field>
        </FieldRow>
        <FieldRow cols={3}>
          <Field label="Type" htmlFor="room-type">
            <Select
              id="room-type"
              value={form.room_type}
              onChange={(e) => set({ room_type: e.target.value, capacity: String(BEDS_FOR[e.target.value] ?? 4) })}
            >
              {OPTIONS.roomType.map((t) => (
                <option key={t} value={t}>
                  {label(t)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Beds" htmlFor="room-capacity" help={fixed ? `A ${label(form.room_type).toLowerCase()} room has ${fixed}.` : "4 to 12 beds."} error={errors.capacity}>
            <Input id="room-capacity" type="number" min={fixed ?? 4} max={fixed ?? 12} disabled={!!fixed} value={fixed ? String(fixed) : form.capacity} onChange={(e) => set({ capacity: e.target.value })} />
          </Field>
          <Field label="Monthly rent (NPR)" htmlFor="room-rate" help="Billed each month to each resident.">
            <Input id="room-rate" type="number" min={0} step={100} value={form.monthly_rate_npr} onChange={(e) => set({ monthly_rate_npr: e.target.value })} />
          </Field>
        </FieldRow>
        <Field label="Status" htmlFor="room-status" help="Rooms under maintenance or closed can't receive new residents.">
          <Select id="room-status" value={form.status} onChange={(e) => set({ status: e.target.value })}>
            {OPTIONS.roomStatus.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </Select>
        </Field>
        <FormError error={mutation.error} />
      </div>
    </Modal>
  );
}

export function AllocateModal({
  bed,
  roomLabel,
  onClose,
}: {
  bed: { id: string; bed_label: string };
  roomLabel: string;
  onClose: () => void;
}) {
  const allocate = useAllocate();
  const [student, setStudent] = useState<Student | null>(null);
  const [from, setFrom] = useState(todayISO());
  return (
    <Modal
      open
      onClose={onClose}
      busy={allocate.isPending}
      title={`Allocate bed ${bed.bed_label}`}
      description={roomLabel}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={allocate.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={allocate.isPending}
            disabled={!student || !from}
            onClick={() =>
              student &&
              allocate.mutate(
                { student_id: student.id, bed_id: bed.id, from_date: from },
                {
                  onSuccess: () => {
                    toast.success("Bed allocated", `${student.full_name} has been notified.`);
                    onClose();
                  },
                },
              )
            }
          >
            Allocate bed
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Resident" htmlFor="allocate-student" help="Only active residents without a bed are listed.">
          <StudentPicker
            id="allocate-student"
            value={student}
            onChange={setStudent}
            filter={(s) => !s.room && s.status !== "ALUMNI" && s.status !== "SUSPENDED"}
            emptyHint="No resident without a bed matches that search."
          />
        </Field>
        <Field label="Moving in on" htmlFor="allocate-from">
          <Input id="allocate-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <FormError error={allocate.error} />
      </div>
    </Modal>
  );
}
