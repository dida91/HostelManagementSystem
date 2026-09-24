import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { BlockCreate, BlockUpdate, RoomCreate, RoomUpdate } from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useBlocks(enabled = true) {
  return useQuery({ queryKey: ["blocks"], queryFn: api.rooms.blocks, enabled });
}

export function useRooms(params: { block_id?: string; status?: string } = {}, enabled = true) {
  return useQuery({ queryKey: ["rooms", params], queryFn: () => api.rooms.list(params), enabled });
}

export function useRoom(id: string | null | undefined) {
  return useQuery({
    queryKey: ["room", id],
    queryFn: () => api.rooms.get(id as string),
    enabled: !!id,
  });
}

const STRUCTURE = ["blocks", "rooms", "room", "analytics"];
const OCCUPANCY = ["rooms", "room", "blocks", "students", "student", "analytics"];

export function useCreateBlock() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: BlockCreate) => api.rooms.createBlock(body),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useUpdateBlock() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: BlockUpdate }) => api.rooms.updateBlock(id, body),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useDeleteBlock() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.rooms.deleteBlock(id),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useCreateRoom() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: RoomCreate) => api.rooms.create(body),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useUpdateRoom() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: RoomUpdate }) => api.rooms.update(id, body),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useDeleteRoom() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.rooms.remove(id),
    onSuccess: () => refresh(...STRUCTURE),
  });
}

export function useSetBedStatus() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ bedId, status }: { bedId: string; status: string }) =>
      api.rooms.setBed(bedId, status),
    onSuccess: () => refresh(...OCCUPANCY),
  });
}

export function useAllocate() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: api.rooms.allocate,
    onSuccess: () => refresh(...OCCUPANCY),
  });
}

export function useVacate() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (assignmentId: string) => api.rooms.vacate(assignmentId),
    onSuccess: () => refresh(...OCCUPANCY),
  });
}
