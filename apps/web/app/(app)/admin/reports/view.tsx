"use client";

import { FileDown, FileSpreadsheet, Lock } from "lucide-react";
import { useState } from "react";

import { Guard } from "@/components/shell/guard";
import { Button, Field, FieldRow, Input, PageHeader, Panel, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/client";
import { periodLabel, recentPeriods, todayISO } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useMe } from "@/lib/queries";
import { toast } from "@/lib/store";

type Kind = "students" | "occupancy" | "fees" | "complaints" | "leave";

function DownloadButtons({ kind, filters }: { kind: Kind; filters: Record<string, string | undefined> }) {
  const [busy, setBusy] = useState<"xlsx" | "pdf" | null>(null);
  const run = async (format: "xlsx" | "pdf") => {
    setBusy(format);
    try {
      await api.reports.download(kind, format, filters);
      toast.success("Report downloaded", "The download is recorded in the audit log.");
    } catch (e) {
      toast.error("Report not downloaded", e instanceof ApiError ? e.message : "Try again in a moment.");
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      <Button icon={FileSpreadsheet} loading={busy === "xlsx"} disabled={!!busy} onClick={() => run("xlsx")}>
        Excel
      </Button>
      <Button icon={FileDown} loading={busy === "pdf"} disabled={!!busy} onClick={() => run("pdf")}>
        PDF
      </Button>
    </div>
  );
}

function DateRange({ id, from, to, onChange }: { id: string; from: string; to: string; onChange: (from: string, to: string) => void }) {
  return (
    <FieldRow>
      <Field label="From" htmlFor={`${id}-from`}>
        <Input id={`${id}-from`} type="date" value={from} max={to} onChange={(e) => onChange(e.target.value, to)} />
      </Field>
      <Field label="To" htmlFor={`${id}-to`}>
        <Input id={`${id}-to`} type="date" value={to} min={from} max={todayISO()} onChange={(e) => onChange(from, e.target.value)} />
      </Field>
    </FieldRow>
  );
}

function Locked() {
  return (
    <p className="flex items-center gap-2 text-ui text-stone">
      <Lock aria-hidden className="h-4 w-4" />
      Holds residents’ personal data, so only the warden can download it.
    </p>
  );
}

function Reports() {
  const { data: me } = useMe();
  const personal = can(me?.role, "exportPersonalReports");
  const [studentStatus, setStudentStatus] = useState("ACTIVE");
  const [feePeriod, setFeePeriod] = useState("");
  const [complaints, setComplaints] = useState({ from: todayISO(-29), to: todayISO() });
  const [leave, setLeave] = useState({ from: todayISO(-29), to: todayISO() });

  return (
    <>
      <PageHeader
        title="Reports"
        description="Registers to print or share, as Excel or PDF. Every download is recorded, and Nepali text prints correctly in PDFs."
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Resident register" description="Contact, college, room and guardian details.">
          {personal ? (
            <div className="space-y-4">
              <Field label="Residents" htmlFor="rep-status">
                <Select id="rep-status" value={studentStatus} onChange={(e) => setStudentStatus(e.target.value)}>
                  <option value="">Everyone</option>
                  {OPTIONS.studentStatus.map((s) => (
                    <option key={s} value={s}>
                      {label(s)}
                    </option>
                  ))}
                </Select>
              </Field>
              <DownloadButtons kind="students" filters={{ status: studentStatus || undefined }} />
            </div>
          ) : (
            <Locked />
          )}
        </Panel>

        <Panel title="Occupancy" description="Every room with its beds, rent and current residents.">
          <DownloadButtons kind="occupancy" filters={{}} />
        </Panel>

        <Panel title="Fees" description="Balances for every resident, and one month's invoices (or all unpaid ones).">
          {personal ? (
            <div className="space-y-4">
              <Field label="Invoices for" htmlFor="rep-period">
                <Select id="rep-period" value={feePeriod} onChange={(e) => setFeePeriod(e.target.value)}>
                  <option value="">All unpaid invoices</option>
                  {recentPeriods().map((p) => (
                    <option key={p} value={p}>
                      {periodLabel(p)}
                    </option>
                  ))}
                </Select>
              </Field>
              <DownloadButtons kind="fees" filters={{ period: feePeriod || undefined }} />
            </div>
          ) : (
            <Locked />
          )}
        </Panel>

        <Panel title="Complaints" description="By category and in detail. Who filed each complaint is left out on purpose.">
          <div className="space-y-4">
            <DateRange id="rep-complaints" from={complaints.from} to={complaints.to} onChange={(from, to) => setComplaints({ from, to })} />
            <DownloadButtons kind="complaints" filters={{ date_from: complaints.from, date_to: complaints.to }} />
          </div>
        </Panel>

        <Panel title="Leave register" description="Who was away, when, and the decision.">
          <div className="space-y-4">
            <DateRange id="rep-leave" from={leave.from} to={leave.to} onChange={(from, to) => setLeave({ from, to })} />
            <DownloadButtons kind="leave" filters={{ date_from: leave.from, date_to: leave.to }} />
          </div>
        </Panel>
      </div>
    </>
  );
}

export function ReportsView() {
  return (
    <Guard capability="exportReports">
      <Reports />
    </Guard>
  );
}
