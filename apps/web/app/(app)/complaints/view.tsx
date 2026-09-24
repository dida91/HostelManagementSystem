"use client";

import { MessageSquareWarning, Send } from "lucide-react";
import { useState } from "react";

import { ResidentOnly } from "@/components/shell/guard";
import {
  Button,
  type Column,
  DataTable,
  Details,
  Drawer,
  EnumPill,
  ErrorState,
  Field,
  FormError,
  PageHeader,
  Pagination,
  Panel,
  SkeletonLines,
  Textarea,
} from "@/components/ui";
import type { Complaint } from "@/lib/api/types";
import { formatDateTime, timeAgo } from "@/lib/format";
import { label } from "@/lib/labels";
import { useComplaint, useComplaints, useFileComplaint } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 10;
const MIN = 10;
const MAX = 4000;

function ReportForm() {
  const [text, setText] = useState("");
  const file = useFileComplaint();
  const length = text.trim().length;
  return (
    <Panel title="Report a problem" description="Say what's wrong and where. English or Nepali are both fine.">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          file.mutate(text.trim(), {
            onSuccess: () => {
              setText("");
              toast.success("Report sent", "The office will sort it and keep you updated.");
            },
          });
        }}
      >
        <Field
          label="What's wrong?"
          htmlFor="complaint-text"
          help={length < MIN ? `At least ${MIN} characters.` : `${length} / ${MAX} characters`}
        >
          <Textarea
            id="complaint-text"
            rows={6}
            maxLength={MAX}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="The tap in the second-floor bathroom has been leaking since Monday."
          />
        </Field>
        <FormError error={file.error} />
        <Button type="submit" variant="primary" icon={Send} loading={file.isPending} disabled={length < MIN}>
          Send report
        </Button>
      </form>
    </Panel>
  );
}

function ComplaintDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const complaint = useComplaint(id);
  const c = complaint.data;
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title="Your report"
      description={c && <EnumPill domain="complaintStatus" value={c.status} />}
    >
      {complaint.isError ? (
        <ErrorState error={complaint.error} onRetry={() => complaint.refetch()} />
      ) : !c ? (
        <SkeletonLines lines={6} />
      ) : (
        <div className="space-y-7">
          <section>
            <h3 className="t-sub mb-2">What you wrote</h3>
            <blockquote className="whitespace-pre-wrap rounded-panel border border-hairline bg-lake-900/60 p-4 text-body text-snow">
              {c.raw_text}
            </blockquote>
          </section>
          <section>
            <h3 className="t-sub mb-3">How it was sorted</h3>
            {c.category || c.priority ? (
              <Details
                items={[
                  ["Category", label(c.category)],
                  ["Priority", c.priority ? <EnumPill domain="priority" value={c.priority} /> : "—"],
                  ["Sent to", label(c.department)],
                  ["Location", c.location ?? "—"],
                ]}
              />
            ) : (
              <p className="text-ui text-stone">Not sorted yet.</p>
            )}
          </section>
          <Details
            items={[
              ["Filed", formatDateTime(c.created_at)],
              ["Resolved", c.resolved_at ? formatDateTime(c.resolved_at) : "Not yet"],
            ]}
          />
        </div>
      )}
    </Drawer>
  );
}

function Resident() {
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const list = useComplaints({ limit: PAGE, offset });

  const columns: Column<Complaint>[] = [
    {
      key: "text",
      header: "Report",
      cell: (c) => (
        <span className="line-clamp-2 max-w-[46ch] text-snow">{c.summary ?? c.raw_text}</span>
      ),
    },
    { key: "status", header: "Status", cell: (c) => <EnumPill domain="complaintStatus" value={c.status} /> },
    {
      key: "filed",
      header: "Filed",
      hideBelow: "sm",
      cell: (c) => <span className="whitespace-nowrap text-mist">{timeAgo(c.created_at)}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Complaints"
        description="Tell the office what needs fixing. Staff can see every report, and you'll be notified as it moves."
      />
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <ReportForm />
        <Panel title="Your reports" flush>
          <DataTable
            columns={columns}
            rows={list.data?.items}
            rowKey={(c) => c.id}
            loading={list.isFetching}
            error={list.error}
            onRetry={() => list.refetch()}
            onRowClick={(c) => setOpenId(c.id)}
            rowLabel={(c) => `Open report: ${(c.summary ?? c.raw_text).slice(0, 60)}`}
            selectedKey={openId}
            empty={{
              icon: MessageSquareWarning,
              title: "Nothing reported yet",
              description: "Reports you send appear here with their progress.",
            }}
            footer={
              list.data && list.data.total > 0 ? (
                <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
              ) : null
            }
          />
        </Panel>
      </div>
      <ComplaintDrawer id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}

export function ComplaintsView() {
  return (
    <ResidentOnly officeHref="/admin/complaints" officeLabel="Open complaint triage">
      <Resident />
    </ResidentOnly>
  );
}
