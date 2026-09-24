"use client";

import { Ellipsis, Library, RefreshCw, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Guard } from "@/components/shell/guard";
import {
  Button,
  type Column,
  ConfirmDialog,
  DataTable,
  EnumPill,
  Field,
  FieldRow,
  FileDrop,
  FormError,
  IconButton,
  Input,
  Menu,
  Modal,
  PageHeader,
  Pagination,
  Panel,
  Select,
  Spinner,
} from "@/components/ui";
import type { HostelDocument } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { useDeleteDocument, useDocuments, useReindexDocument, useUploadDocument } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 15;
const MAX_MB = 20;

function UploadModal({ onClose }: { onClose: () => void }) {
  const upload = useUploadDocument();
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("HOSTEL_RULES");
  const [language, setLanguage] = useState("en");
  const [file, setFile] = useState<File | null>(null);
  const tooBig = file ? file.size > MAX_MB * 1024 * 1024 : false;
  return (
    <Modal
      open
      onClose={onClose}
      busy={upload.isPending}
      title="Upload a document"
      description="The assistant answers rules and policy questions from these. Reading and indexing happen in the background."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={upload.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon={Upload}
            loading={upload.isPending}
            disabled={!file || tooBig || title.trim().length < 2}
            onClick={() => {
              if (!file) return;
              const form = new FormData();
              form.append("file", file);
              form.append("title", title.trim());
              form.append("doc_type", docType);
              form.append("language", language);
              upload.mutate(form, {
                onSuccess: () => {
                  toast.success("Document uploaded", "It's being read and indexed. This takes a minute or two.");
                  onClose();
                },
              });
            }}
          >
            Upload
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Title" htmlFor="doc-title" required>
          <Input id="doc-title" maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Hostel rules 2026" />
        </Field>
        <FieldRow>
          <Field label="Kind of document" htmlFor="doc-type">
            <Select id="doc-type" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {OPTIONS.documentType.map((t) => (
                <option key={t} value={t}>
                  {label(t)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Language" htmlFor="doc-language">
            <Select id="doc-language" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">English</option>
              <option value="ne">Nepali</option>
            </Select>
          </Field>
        </FieldRow>
        <FileDrop accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" file={file} onFile={setFile} hint={`PDF, text or Markdown, up to ${MAX_MB} MB.`} />
        {tooBig && <p className="text-small text-laligurans-300">That file is over {MAX_MB} MB.</p>}
        <FormError error={upload.error} />
      </div>
    </Modal>
  );
}

function Documents() {
  const [offset, setOffset] = useState(0);
  const list = useDocuments({ limit: PAGE, offset });
  const reindex = useReindexDocument();
  const remove = useDeleteDocument();
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<HostelDocument | null>(null);

  const columns: Column<HostelDocument>[] = [
    {
      key: "title",
      header: "Document",
      cell: (d) => (
        <span className="text-snow">
          {d.title}
          <span className="block text-small text-stone">{d.filename}</span>
        </span>
      ),
    },
    { key: "type", header: "Kind", hideBelow: "md", cell: (d) => <span className="text-mist">{label(d.doc_type)}</span> },
    {
      key: "status",
      header: "Status",
      cell: (d) => (
        <span className="inline-flex items-center gap-2">
          {(d.status === "UPLOADED" || d.status === "PROCESSING") && <Spinner className="text-glacier" />}
          <EnumPill domain="documentStatus" value={d.status} />
        </span>
      ),
    },
    { key: "pages", header: "Pages", align: "right", hideBelow: "sm", cell: (d) => d.page_count ?? "—" },
    { key: "chunks", header: "Passages", align: "right", hideBelow: "sm", cell: (d) => d.chunk_count },
    { key: "uploaded", header: "Uploaded", hideBelow: "lg", cell: (d) => <span className="whitespace-nowrap text-mist">{formatDate(d.created_at)}</span> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (d) => (
        <Menu
          label={`${d.title} actions`}
          items={[
            {
              label: "Read and index again",
              icon: RefreshCw,
              onSelect: () =>
                reindex.mutate(d.id, {
                  onSuccess: () => toast.success("Indexing again", d.title),
                  onError: (e) => toast.error("Couldn't start indexing", e.message),
                }),
            },
            { label: "Delete document", icon: Trash2, tone: "danger", onSelect: () => setDeleting(d) },
          ]}
          trigger={(props) => <IconButton {...props} icon={Ellipsis} label={`${d.title} actions`} size="sm" />}
        />
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Documents"
        description="Hostel rules and policies the assistant answers from, with citations. A document must be indexed before it can be used."
        actions={
          <Button variant="primary" icon={Upload} onClick={() => setUploading(true)}>
            Upload document
          </Button>
        }
      />
      <Panel flush>
        <DataTable
          columns={columns}
          rows={list.data?.items}
          rowKey={(d) => d.id}
          loading={list.isFetching && !list.data}
          error={list.error}
          onRetry={() => list.refetch()}
          empty={{
            icon: Library,
            title: "No documents yet",
            description: "Until the rules are uploaded, the assistant can't answer policy questions.",
            action: (
              <Button variant="primary" icon={Upload} onClick={() => setUploading(true)}>
                Upload document
              </Button>
            ),
          }}
          footer={list.data && list.data.total > 0 ? <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
        />
      </Panel>
      {uploading && <UploadModal onClose={() => setUploading(false)} />}
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title={`Delete ${deleting?.title ?? "document"}?`}
        confirmLabel="Delete document"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() =>
          deleting &&
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Document deleted");
              setDeleting(null);
            },
          })
        }
      >
        <p>The file and its index are removed. The assistant stops using it straight away.</p>
      </ConfirmDialog>
    </>
  );
}

export function DocumentsView() {
  return (
    <Guard capability="manageDocuments" title="Documents are managed by the warden" description="Ask the warden to upload or change hostel documents.">
      <Documents />
    </Guard>
  );
}
