"use client";

import { UserPlus, Users } from "lucide-react";
import { useState } from "react";

import { Guard } from "@/components/shell/guard";
import {
  Avatar,
  Button,
  type Column,
  DataTable,
  EnumPill,
  PageHeader,
  Pagination,
  Panel,
  SearchInput,
  Select,
  Tag,
  useDebounced,
} from "@/components/ui";
import type { Student } from "@/lib/api/types";
import { label, OPTIONS } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useMe, useStudents } from "@/lib/queries";

import { RegisterModal } from "./modals";
import { StudentDrawer } from "./student-drawer";

const PAGE = 15;

function Students() {
  const { data: me } = useMe();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ACTIVE");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const q = useDebounced(query.trim(), 300);
  const list = useStudents({ q: q || undefined, status: status || undefined, limit: PAGE, offset });

  if (!me) return null;
  const columns: Column<Student>[] = [
    {
      key: "resident",
      header: "Resident",
      cell: (s) => (
        <span className="flex items-center gap-3">
          <Avatar name={s.full_name} size="sm" />
          <span className="min-w-0 leading-tight">
            <span className="block truncate text-snow">{s.full_name}</span>
            <span className="block truncate text-small text-stone">{s.email}</span>
            {!s.is_active && s.status === "ACTIVE" && (
              <span className="mt-1 block sm:hidden">
                <Tag>Sign-in off</Tag>
              </span>
            )}
          </span>
        </span>
      ),
    },
    { key: "code", header: "Code", hideBelow: "sm", cell: (s) => <span className="whitespace-nowrap text-mist">{s.student_code}</span> },
    { key: "room", header: "Room", cell: (s) => (s.room ? <span className="sm:whitespace-nowrap">{s.room}</span> : <span className="text-stone">No bed</span>) },
    { key: "college", header: "College", hideBelow: "lg", cell: (s) => <span className="text-mist">{s.college ?? "—"}</span> },
    {
      key: "status",
      header: "Status",
      hideBelow: "sm",
      cell: (s) => (
        <span className="flex flex-wrap gap-1.5">
          <EnumPill domain="studentStatus" value={s.status} />
          {!s.is_active && s.status === "ACTIVE" && <Tag>Sign-in off</Tag>}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Students"
        description="Everyone registered with the hostel. Select a resident to see their profile, fees and sign-in."
        actions={
          can(me.role, "manageStudents") && (
            <Button variant="primary" icon={UserPlus} onClick={() => setRegistering(true)}>
              Register a student
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <SearchInput
          className="sm:max-w-sm sm:flex-1"
          label="Search residents"
          placeholder="Search by name, email or code"
          value={query}
          onChange={(v) => {
            setQuery(v);
            setOffset(0);
          }}
        />
        <Select
          aria-label="Filter by status"
          className="min-h-10 sm:w-48"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {OPTIONS.studentStatus.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </Select>
      </div>
      <Panel flush>
        <DataTable
          columns={columns}
          rows={list.data?.items}
          rowKey={(s) => s.id}
          loading={list.isFetching}
          error={list.error}
          onRetry={() => list.refetch()}
          onRowClick={(s) => setSelected(s.id)}
          rowLabel={(s) => `Open ${s.full_name}`}
          selectedKey={selected}
          empty={{
            icon: Users,
            title: q ? "No one matches that search" : "No residents in this view",
            description: q ? "Try part of their name, their email or student code." : undefined,
          }}
          footer={list.data && list.data.total > 0 ? <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
        />
      </Panel>
      <StudentDrawer id={selected} me={me} onClose={() => setSelected(null)} />
      {registering && (
        <RegisterModal
          onClose={() => setRegistering(false)}
          onCreated={(s) => {
            setRegistering(false);
            setSelected(s.id);
          }}
        />
      )}
    </>
  );
}

export function StudentsView() {
  return (
    <Guard capability="manageStudents">
      <Students />
    </Guard>
  );
}
