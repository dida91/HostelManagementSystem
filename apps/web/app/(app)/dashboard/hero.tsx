"use client";

import { HorizonStage } from "@/components/three/horizon-stage";
import { greeting } from "@/lib/format";

const today = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" });

/** The horizon band: the day's greeting against Machhapuchhre at dusk. */
export function Hero({ name, children }: { name: string; children?: React.ReactNode }) {
  const first = name.split(/\s+/)[0] ?? name;
  return (
    <HorizonStage variant="band" className="mb-8 rounded-stage border border-hairline shadow-panel">
      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-to-t from-lake-950/95 via-lake-950/40 to-transparent sm:bg-gradient-to-r sm:from-lake-950/90 sm:via-lake-950/35 sm:to-transparent"
      />
      <div className="relative flex min-h-[280px] flex-col justify-end gap-5 p-6 sm:min-h-[300px] sm:p-9">
        <div className="animate-light-rise">
          <p className="text-ui text-mist">{today.format(new Date())}</p>
          <h1 className="t-display mt-1 text-balance text-snow" style={{ fontSize: "clamp(34px, 4.6vw, 52px)" }}>
            {greeting()}, {first}
          </h1>
        </div>
        {children}
      </div>
    </HorizonStage>
  );
}
