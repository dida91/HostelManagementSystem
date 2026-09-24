"use client";

import { Ellipsis, Megaphone, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  Button,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  fieldErrors,
  FieldRow,
  FormError,
  IconButton,
  Input,
  Menu,
  Modal,
  PageHeader,
  Select,
  SkeletonLines,
  StatusPill,
  Tag,
  Textarea,
} from "@/components/ui";
import type { Notice } from "@/lib/api/types";
import { formatDateTime, timeAgo } from "@/lib/format";
import { audienceLabel, OPTIONS } from "@/lib/labels";
import { can, isStaff } from "@/lib/permissions";
import { useCreateNotice, useDeleteNotice, useMe, useNotices, useUpdateNotice } from "@/lib/queries";
import { toast } from "@/lib/store";

/** <input type="datetime-local"> value for an ISO timestamp, in local time. */
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function windowOf(n: Notice): { label: string; tone: "success" | "info" | "neutral" } {
  const now = Date.now();
  if (new Date(n.publish_at).getTime() > now) return { label: "Scheduled", tone: "info" };
  if (n.expires_at && new Date(n.expires_at).getTime() < now) return { label: "Expired", tone: "neutral" };
  return { label: "Live", tone: "success" };
}

function NoticeModal({ notice, open, onClose }: { notice: Notice | null; open: boolean; onClose: () => void }) {
  const create = useCreateNotice();
  const update = useUpdateNotice();
  const mutation = notice ? update : create;
  const [form, setForm] = useState({
    title: notice?.title ?? "",
    body: notice?.body ?? "",
    audience: notice?.audience ?? "ALL",
    publish_at: toLocalInput(notice?.publish_at),
    expires_at: toLocalInput(notice?.expires_at),
  });
  const errors = fieldErrors(mutation.error);
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const valid = form.title.trim().length >= 3 && form.body.trim().length >= 3;
  const badWindow = form.publish_at && form.expires_at && form.expires_at <= form.publish_at;

  const submit = () => {
    const body = {
      title: form.title.trim(),
      body: form.body.trim(),
      audience: form.audience as "ALL",
      publish_at: form.publish_at ? new Date(form.publish_at).toISOString() : null,
      expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
    };
    const done = (verb: string) => () => {
      toast.success(verb, body.publish_at && new Date(body.publish_at) > new Date() ? "Residents will be notified when it goes live." : undefined);
      onClose();
    };
    if (notice) update.mutate({ id: notice.id, body }, { onSuccess: done("Notice updated") });
    else create.mutate({ ...body, publish_at: body.publish_at ?? undefined }, { onSuccess: done("Notice posted") });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      busy={mutation.isPending}
      size="lg"
      title={notice ? "Edit notice" : "Post a notice"}
      description={notice ? "People already notified won't be notified again." : "Everyone in the audience is notified when it goes live."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button variant="primary" loading={mutation.isPending} disabled={!valid || !!badWindow} onClick={submit}>
            {notice ? "Save notice" : "Post notice"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Title" htmlFor="notice-title" required error={errors.title}>
          <Input id="notice-title" maxLength={200} value={form.title} onChange={(e) => set({ title: e.target.value })} placeholder="Water supply maintenance on Saturday" />
        </Field>
        <Field label="Message" htmlFor="notice-body" required error={errors.body}>
          <Textarea id="notice-body" rows={6} maxLength={10000} value={form.body} onChange={(e) => set({ body: e.target.value })} />
        </Field>
        <Field label="Who sees it" htmlFor="notice-audience">
          <Select id="notice-audience" value={form.audience} onChange={(e) => set({ audience: e.target.value })}>
            {OPTIONS.audience.map((a) => (
              <option key={a} value={a}>
                {audienceLabel(a)}
              </option>
            ))}
          </Select>
        </Field>
        <FieldRow>
          <Field label="Publish" htmlFor="notice-publish" help="Leave empty to publish now.">
            <Input id="notice-publish" type="datetime-local" value={form.publish_at} onChange={(e) => set({ publish_at: e.target.value })} />
          </Field>
          <Field label="Take down" htmlFor="notice-expires" help="Optional." error={badWindow ? "Must be after it's published." : errors.expires_at}>
            <Input id="notice-expires" type="datetime-local" value={form.expires_at} invalid={!!badWindow} onChange={(e) => set({ expires_at: e.target.value })} />
          </Field>
        </FieldRow>
        <FormError error={mutation.error} />
      </div>
    </Modal>
  );
}

export function NoticesView() {
  const { data: me } = useMe();
  const staff = isStaff(me?.role);
  const manage = can(me?.role, "manageNotices");
  const [showAll, setShowAll] = useState(false);
  const notices = useNotices(staff && showAll);
  const [editing, setEditing] = useState<Notice | null>(null);
  const [composing, setComposing] = useState(false);
  const [deleting, setDeleting] = useState<Notice | null>(null);
  const remove = useDeleteNotice();

  return (
    <>
      <PageHeader
        title="Notices"
        description={manage ? "Tell residents and staff what's happening. Everyone in the audience is notified." : "Announcements from the hostel office."}
        actions={
          manage && (
            <Button variant="primary" icon={Megaphone} onClick={() => setComposing(true)}>
              Post a notice
            </Button>
          )
        }
      />
      {staff && (
        <Checkbox className="mb-5" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} label="Include scheduled and expired notices" />
      )}

      {notices.isPending ? (
        <div className="panel p-4 sm:p-6">
          <SkeletonLines lines={5} />
        </div>
      ) : notices.isError ? (
        <div className="panel">
          <ErrorState error={notices.error} onRetry={() => notices.refetch()} />
        </div>
      ) : notices.data.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={Megaphone}
            title="No notices right now"
            description={manage ? "Post one and everyone in its audience is notified." : "New announcements from the office will appear here."}
            action={manage && <Button variant="primary" onClick={() => setComposing(true)}>Post a notice</Button>}
          />
        </div>
      ) : (
        <div className="space-y-4">
          {notices.data.map((n) => {
            const state = windowOf(n);
            return (
              <article key={n.id} className="panel max-w-3xl p-4 sm:p-6">
                <header className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="t-heading text-snow">{n.title}</h2>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-small text-stone">
                      {staff && <StatusPill tone={state.tone}>{state.label}</StatusPill>}
                      {staff && <Tag>{audienceLabel(n.audience)}</Tag>}
                      <span>
                        {state.label === "Scheduled" ? `Goes live ${formatDateTime(n.publish_at)}` : `Posted ${timeAgo(n.publish_at)}`}
                      </span>
                      {n.expires_at && <span>Until {formatDateTime(n.expires_at)}</span>}
                    </div>
                  </div>
                  {manage && (
                    <Menu
                      label={`Actions for ${n.title}`}
                      items={[
                        { label: "Edit notice", icon: Pencil, onSelect: () => setEditing(n) },
                        { label: "Delete notice", icon: Trash2, tone: "danger", onSelect: () => setDeleting(n) },
                      ]}
                      trigger={(props) => <IconButton {...props} icon={Ellipsis} label={`Actions for ${n.title}`} size="sm" />}
                    />
                  )}
                </header>
                <p className="mt-4 max-w-[68ch] whitespace-pre-wrap text-body text-mist">{n.body}</p>
              </article>
            );
          })}
        </div>
      )}

      {(composing || editing) && (
        <NoticeModal
          key={editing?.id ?? "new"}
          notice={editing}
          open
          onClose={() => {
            setComposing(false);
            setEditing(null);
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete this notice?"
        confirmLabel="Delete notice"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() =>
          deleting &&
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Notice deleted");
              setDeleting(null);
            },
          })
        }
      >
        <p>
          “{deleting?.title}” disappears for everyone. Notifications already sent stay in people’s inboxes.
        </p>
      </ConfirmDialog>
    </>
  );
}
