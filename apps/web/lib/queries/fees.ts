import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  FeeStructureCreate,
  FeeStructureUpdate,
  InvoiceCreate,
  PaymentCreate,
} from "@/lib/api/types";

import { useInvalidate } from "./shared";

export function useBalance(studentId?: string, enabled = true) {
  return useQuery({
    queryKey: ["balance", studentId ?? "me"],
    queryFn: () => api.fees.balance(studentId),
    enabled,
  });
}

export function useLedger(studentId?: string, enabled = true) {
  return useQuery({
    queryKey: ["ledger", studentId ?? "me"],
    queryFn: () => api.fees.ledger(studentId),
    enabled,
  });
}

export function useInvoices(
  params: { student_id?: string; status?: string; billing_period?: string; limit?: number; offset?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: ["invoices", params],
    queryFn: () => api.fees.invoices(params),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useInvoice(id: string | null | undefined) {
  return useQuery({
    queryKey: ["invoice", id],
    queryFn: () => api.fees.invoice(id as string),
    enabled: !!id,
  });
}

export function useFeeStructures(enabled = true) {
  return useQuery({ queryKey: ["structures"], queryFn: api.fees.structures, enabled });
}

const MONEY = ["invoices", "invoice", "balance", "ledger", "analytics", "notifications"];

export function useCreateInvoice() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: InvoiceCreate) => api.fees.createInvoice(body),
    onSuccess: () => refresh(...MONEY),
  });
}

export function useGenerateInvoices() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ period, dueDay }: { period?: string; dueDay?: number }) =>
      api.fees.generate(period, dueDay),
    onSuccess: () => refresh(...MONEY),
  });
}

export function useRecordPayment() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ body, key }: { body: PaymentCreate; key: string }) =>
      api.fees.recordPayment(body, key),
    onSuccess: () => refresh(...MONEY),
  });
}

export function useCreateStructure() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (body: FeeStructureCreate) => api.fees.createStructure(body),
    onSuccess: () => refresh("structures"),
  });
}

export function useUpdateStructure() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: FeeStructureUpdate }) =>
      api.fees.updateStructure(id, body),
    onSuccess: () => refresh("structures"),
  });
}

export function useDeleteStructure() {
  const refresh = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.fees.deleteStructure(id),
    onSuccess: () => refresh("structures"),
  });
}
