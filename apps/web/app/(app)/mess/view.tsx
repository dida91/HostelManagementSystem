"use client";

import { Pencil, Plus, Send, Star, Trash2, UtensilsCrossed } from "lucide-react";
import { useState } from "react";

import { BarList } from "@/components/charts";
import {
  Button,
  type Column,
  ConfirmDialog,
  DataTable,
  EnumPill,
  Field,
  FieldRow,
  FormError,
  IconButton,
  Input,
  Kpi,
  Modal,
  PageHeader,
  Pagination,
  Panel,
  RatingInput,
  Segmented,
  Select,
  SkeletonLines,
  Tag,
  Textarea,
} from "@/components/ui";
import type { MenuItem, MessFeedback } from "@/lib/api/types";
import { formatDate, todayISO, WEEKDAYS } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { can, isStaff } from "@/lib/permissions";
import { useAnalytics, useFeedback, useMe, useMenu, useRemoveMenu, useSetMenu, useSubmitFeedback } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 10;

function MenuModal({
  day,
  meal,
  current,
  onClose,
}: {
  day: number;
  meal: string | null;
  current: MenuItem | undefined;
  onClose: () => void;
}) {
  const save = useSetMenu();
  const remove = useRemoveMenu();
  const [items, setItems] = useState(current?.items ?? "");
  const [time, setTime] = useState(current?.serving_time ?? "");
  const [confirm, setConfirm] = useState(false);
  if (!meal) return null;
  const busy = save.isPending || remove.isPending;
  return (
    <>
      <Modal
        open={!!meal && !confirm}
        onClose={onClose}
        busy={busy}
        title={`${label(meal)}, ${WEEKDAYS[day]}`}
        description="What residents will see on the menu."
        footer={
          <>
            {current && (
              <Button variant="ghost" icon={Trash2} className="mr-auto" onClick={() => setConfirm(true)} disabled={busy}>
                Stop serving
              </Button>
            )}
            <Button variant="ghost" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={save.isPending}
              disabled={!items.trim()}
              onClick={() =>
                save.mutate(
                  { day, meal, items: items.trim(), servingTime: time.trim() || null },
                  {
                    onSuccess: () => {
                      toast.success("Menu updated", `${label(meal)} on ${WEEKDAYS[day]}.`);
                      onClose();
                    },
                  },
                )
              }
            >
              Save menu
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="What's served" htmlFor="menu-items" required>
            <Textarea id="menu-items" rows={3} maxLength={1000} value={items} onChange={(e) => setItems(e.target.value)} placeholder="Dal, bhat, tarkari, achar" />
          </Field>
          <Field label="Serving time" htmlFor="menu-time" help="For example 07:00–09:00">
            <Input id="menu-time" maxLength={40} value={time} onChange={(e) => setTime(e.target.value)} />
          </Field>
          <FormError error={save.error} />
        </div>
      </Modal>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title={`Stop serving ${label(meal).toLowerCase()} on ${WEEKDAYS[day]}?`}
        confirmLabel="Stop serving"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() =>
          remove.mutate(
            { day, meal },
            {
              onSuccess: () => {
                toast.success("Removed from the menu");
                setConfirm(false);
                onClose();
              },
            },
          )
        }
      >
        <p>It disappears from the weekly menu. You can add it back any time.</p>
      </ConfirmDialog>
    </>
  );
}

function WeekMenu({ canEdit }: { canEdit: boolean }) {
  const menu = useMenu();
  const today = new Date().getDay();
  const [day, setDay] = useState(String(today));
  const [editing, setEditing] = useState<string | null>(null);
  const dayNum = Number(day);
  const meals = OPTIONS.mealType.map((meal) => ({
    meal,
    item: menu.data?.find((m) => m.day_of_week === dayNum && m.meal_type === meal),
  }));
  return (
    <Panel
      title="Weekly menu"
      description={canEdit ? "Choose a day, then edit any meal." : undefined}
      actions={
        <Segmented
          label="Day of the week"
          value={day}
          onChange={setDay}
          options={WEEKDAYS.map((w, i) => ({ value: String(i), label: i === today ? "Today" : w.slice(0, 3) }))}
        />
      }
    >
      {menu.isPending ? (
        <SkeletonLines lines={4} />
      ) : menu.isError ? (
        <p className="text-ui text-laligurans-300">The menu didn’t load.</p>
      ) : (
        <ul className="rows">
          {meals.map(({ meal, item }) => (
            <li key={meal} className="grid grid-cols-[6.5rem_minmax(0,1fr)_auto] items-center gap-4 py-3.5">
              <span className="text-ui text-stone">{label(meal)}</span>
              {item ? (
                <span className="text-ui text-snow">
                  {item.items}
                  {item.serving_time && <span className="block text-small text-stone">{item.serving_time}</span>}
                </span>
              ) : (
                <span className="text-ui text-stone">Not served</span>
              )}
              {canEdit ? (
                <IconButton
                  icon={item ? Pencil : Plus}
                  label={item ? `Edit ${label(meal).toLowerCase()}` : `Add ${label(meal).toLowerCase()}`}
                  size="sm"
                  onClick={() => setEditing(meal)}
                />
              ) : (
                <span />
              )}
            </li>
          ))}
        </ul>
      )}
      {editing && (
        <MenuModal
          key={`${day}-${editing}`}
          day={dayNum}
          meal={editing}
          current={meals.find((m) => m.meal === editing)?.item}
          onClose={() => setEditing(null)}
        />
      )}
    </Panel>
  );
}

/** The meal most recently served, by the clock: what a resident most likely wants to rate. */
function latestMeal(now = new Date()): string {
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < 12 * 60 + 30) return "BREAKFAST";
  if (minutes < 16 * 60 + 30) return "LUNCH";
  if (minutes < 19 * 60) return "SNACKS";
  return "DINNER";
}

function RateMeal() {
  const submit = useSubmitFeedback();
  // No preset rating: a default would quietly skew the mess averages.
  const [form, setForm] = useState(() => ({ meal_date: todayISO(), meal_type: latestMeal(), rating: 0, comment: "" }));
  return (
    <Panel title="Rate a meal" description="Your rating goes to the mess team. Comments help them fix what's wrong.">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate(
            { ...form, meal_type: form.meal_type as MessFeedback["meal_type"], comment: form.comment.trim() || null },
            {
              onSuccess: () => {
                setForm((f) => ({ ...f, rating: 0, comment: "" }));
                toast.success("Rating sent", "Thank you. The mess team sees every rating.");
              },
            },
          );
        }}
      >
        <FieldRow>
          <Field label="Date" htmlFor="meal-date">
            <Input id="meal-date" type="date" max={todayISO()} value={form.meal_date} onChange={(e) => setForm({ ...form, meal_date: e.target.value })} />
          </Field>
          <Field label="Meal" htmlFor="meal-type">
            <Select id="meal-type" value={form.meal_type} onChange={(e) => setForm({ ...form, meal_type: e.target.value })}>
              {OPTIONS.mealType.map((m) => (
                <option key={m} value={m}>
                  {label(m)}
                </option>
              ))}
            </Select>
          </Field>
        </FieldRow>
        <RatingInput label="How was it?" value={form.rating} onChange={(rating) => setForm({ ...form, rating })} />
        <Field label="Comment" htmlFor="meal-comment" help="Optional. English or Nepali.">
          <Textarea id="meal-comment" rows={3} maxLength={2000} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
        </Field>
        <FormError error={submit.error} />
        <Button type="submit" variant="primary" icon={Send} loading={submit.isPending} disabled={form.rating === 0}>
          Send rating
        </Button>
      </form>
    </Panel>
  );
}

function feedbackColumns(showIssues: boolean): Column<MessFeedback>[] {
  return [
    {
      key: "meal",
      header: "Meal",
      cell: (f) => (
        <span className="whitespace-nowrap text-snow">
          {label(f.meal_type)}
          <span className="block text-small text-stone">{formatDate(f.meal_date)}</span>
        </span>
      ),
    },
    {
      key: "rating",
      header: "Rating",
      cell: (f) => (
        <span className="inline-flex items-center gap-1 whitespace-nowrap text-snow" aria-label={`${f.rating} out of 5`}>
          <Star aria-hidden className="h-3.5 w-3.5 fill-marigold text-marigold" />
          {f.rating}/5
        </span>
      ),
    },
    { key: "comment", header: "Comment", cell: (f) => <span className="line-clamp-2 max-w-[52ch] text-mist">{f.comment ?? "—"}</span> },
    {
      key: "mood",
      header: "Mood",
      hideBelow: "sm",
      cell: (f) => (f.analysis?.sentiment ? <EnumPill domain="sentiment" value={f.analysis.sentiment} /> : <span className="text-stone">—</span>),
    },
    ...(showIssues
      ? ([
          {
            key: "issues",
            header: "Issues noted",
            hideBelow: "lg",
            cell: (f: MessFeedback) =>
              f.analysis?.issues?.length ? (
                <span className="flex flex-wrap gap-1">
                  {f.analysis.issues.slice(0, 3).map((i) => (
                    <Tag key={i}>{i}</Tag>
                  ))}
                </span>
              ) : (
                <span className="text-stone">—</span>
              ),
          },
        ] as Column<MessFeedback>[])
      : []),
  ];
}

function Ratings({ staff }: { staff: boolean }) {
  const [offset, setOffset] = useState(0);
  const feedback = useFeedback({ limit: PAGE, offset });
  return (
    <Panel
      title={staff ? "Residents' ratings" : "Your ratings"}
      description={staff ? "Newest first. Moods and issues are suggested by AI from the comments." : undefined}
      flush
    >
      <DataTable
        columns={feedbackColumns(staff)}
        rows={feedback.data?.items}
        rowKey={(f) => f.id}
        loading={feedback.isFetching}
        error={feedback.error}
        onRetry={() => feedback.refetch()}
        empty={{ icon: UtensilsCrossed, title: "No ratings yet", description: staff ? "Ratings appear as residents send them." : "Rate a meal and it appears here." }}
        footer={
          feedback.data && feedback.data.total > 0 ? (
            <Pagination total={feedback.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
          ) : null
        }
      />
    </Panel>
  );
}

function MessInsights() {
  const analytics = useAnalytics(30);
  const m = analytics.data?.mess;
  const byMeal = OPTIONS.mealType
    .filter((meal) => m?.average_by_meal[meal] !== undefined)
    .map((meal) => ({ key: meal, label: label(meal), value: m?.average_by_meal[meal] ?? 0 }));
  return (
    <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <Kpi
        label="Average rating, 30 days"
        loading={analytics.isPending}
        value={m?.average_rating ? `${m.average_rating} / 5` : "—"}
        context={m ? `${m.responses} ratings` : undefined}
      />
      <Panel title="By meal" description="Average rating out of 5, last 30 days">
        {analytics.isPending ? (
          <SkeletonLines lines={3} />
        ) : byMeal.length === 0 ? (
          <p className="text-ui text-stone">No ratings in the last 30 days.</p>
        ) : (
          <BarList title="Average rating by meal" data={byMeal} max={5} format={(v) => v.toFixed(1)} share={false} />
        )}
      </Panel>
    </div>
  );
}

export function MessView() {
  const { data: me } = useMe();
  if (!me) return null;
  const staff = isStaff(me.role);
  return (
    <>
      <PageHeader
        title="Mess"
        description={staff ? "The weekly menu, and what residents think of the food." : "This week's menu. Rate the meals you eat so the mess team knows what to fix."}
      />
      <div className="space-y-5">
        <WeekMenu canEdit={can(me.role, "editMenu")} />
        {staff ? (
          <>
            <MessInsights />
            <Ratings staff />
          </>
        ) : (
          <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <RateMeal />
            <Ratings staff={false} />
          </div>
        )}
      </div>
    </>
  );
}
