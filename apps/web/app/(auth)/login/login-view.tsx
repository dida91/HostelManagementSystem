"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/shell/brand";
import { HorizonStage } from "@/components/three/horizon-stage";
import { Button, Field, FormError, Input } from "@/components/ui";
import { api } from "@/lib/api";

function safeNext(raw: string | null): string {
  // Only same-site paths: never let a link send someone off-site after sign-in.
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/dashboard";
}

export function LoginView() {
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setExpired(new URLSearchParams(window.location.search).has("expired"));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.auth.login(email.trim(), password);
      // Nothing cached from a previous person on this device may show.
      qc.clear();
      router.replace(safeNext(new URLSearchParams(window.location.search).get("next")));
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <HorizonStage variant="full" className="min-h-dvh">
      {/* Scrim: keeps the form legible over the moving scene. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-t from-lake-950 via-lake-950/40 to-transparent lg:bg-gradient-to-r lg:from-lake-950/95 lg:via-lake-950/60 lg:to-transparent"
      />
      <div className="relative flex min-h-dvh flex-col px-5 py-6 sm:px-10 lg:px-16">
        <header className="flex items-center gap-3">
          <BrandMark className="h-9 w-9" />
          <span className="text-ui text-mist">Girls hostel, Pokhara</span>
        </header>

        <div className="flex flex-1 items-end pb-4 pt-[28vh] lg:items-center lg:py-6">
          <div className="w-full max-w-[420px] animate-light-rise">
            <h1
              className="t-display text-snow"
              style={{ fontSize: "clamp(48px, min(7vw, 11vh), 80px)", lineHeight: 1, fontStretch: "125%" }}
            >
              Kutumba
            </h1>
            <p className="mt-3 max-w-[34ch] text-body text-mist">
              Residents and the hostel office sign in here with the email the office registered.
            </p>

            <form onSubmit={onSubmit} className="glass mt-6 space-y-4 rounded-overlay p-5 shadow-overlay sm:p-6" noValidate>
              {expired && !error && (
                <p className="rounded-control border border-marigold/30 bg-marigold/10 px-3 py-2.5 text-ui text-marigold-300">
                  Your session ended. Sign in again to pick up where you left off.
                </p>
              )}
              <Field label="Email" htmlFor="email">
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field label="Password" htmlFor="password">
                <div className="relative">
                  <Input
                    id="password"
                    type={show ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pr-11"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Hide password" : "Show password"}
                    aria-pressed={show}
                    className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-stone hover:text-snow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
                  >
                    {show ? <EyeOff aria-hidden className="h-4 w-4" /> : <Eye aria-hidden className="h-4 w-4" />}
                  </button>
                </div>
              </Field>
              <FormError error={error} />
              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={busy}
                disabled={!email.trim() || password.length < 8}
                className="w-full"
              >
                Sign in
              </Button>
              <p className="text-small text-stone">
                Forgotten your password? The warden can set a new one for you.
              </p>
            </form>
          </div>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 text-small text-stone">
          <span>Phewa lakeside, Pokhara</span>
          <span>Machhapuchhre at dusk</span>
        </footer>
      </div>
    </HorizonStage>
  );
}
