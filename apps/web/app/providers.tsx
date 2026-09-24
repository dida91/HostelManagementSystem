"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Toaster } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { usePrefs } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // A 4xx will not fix itself on retry; network and 5xx might.
            retry: (count, error) =>
              !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
              count < 2,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
          mutations: { retry: false },
        },
      }),
  );
  const reduceEffects = usePrefs((s) => s.reduceEffects);

  useEffect(() => {
    void usePrefs.persist.rehydrate();
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("reduce-effects", reduceEffects);
  }, [reduceEffects]);

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
