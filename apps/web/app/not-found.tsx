import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-6 text-center">
      <div>
        <p className="t-display text-snow">Not here</p>
        <p className="mx-auto mt-3 max-w-[40ch] text-body text-mist">
          That page doesn’t exist. It may have moved, or the link is incomplete.
        </p>
        <Link
          href="/dashboard"
          className="mt-8 inline-flex h-10 items-center rounded-control bg-marigold px-4 text-ui font-medium text-marigold-ink hover:bg-marigold-300"
        >
          Go to home
        </Link>
      </div>
    </main>
  );
}
