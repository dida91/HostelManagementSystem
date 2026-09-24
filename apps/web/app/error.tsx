"use client";

import { RotateCw } from "lucide-react";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="grid min-h-[60dvh] place-items-center px-6 text-center">
      <div>
        <p className="t-title text-snow">This screen stopped working</p>
        <p className="mx-auto mt-3 max-w-[46ch] text-body text-mist">
          Something unexpected went wrong while showing it. Your data is safe; try loading it again.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-8 inline-flex h-10 items-center gap-2 rounded-control bg-marigold px-4 text-ui font-medium text-marigold-ink hover:bg-marigold-300"
        >
          <RotateCw aria-hidden className="h-4 w-4" />
          Try again
        </button>
      </div>
    </main>
  );
}
