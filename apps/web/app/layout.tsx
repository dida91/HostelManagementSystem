import type { Metadata, Viewport } from "next";
import { Anek_Devanagari, Anek_Latin } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

// One family for both scripts residents write in; the width axis carries hierarchy.
const latin = Anek_Latin({
  subsets: ["latin", "latin-ext"],
  axes: ["wdth"],
  variable: "--font-latin",
  display: "swap",
});
const devanagari = Anek_Devanagari({
  subsets: ["devanagari"],
  axes: ["wdth"],
  variable: "--font-deva",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Kutumba Hostel", template: "%s | Kutumba Hostel" },
  description: "Kutumba 1 Girls Hostel, Pokhara: residents' and office portal",
};

export const viewport: Viewport = {
  themeColor: "#0A1A20",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${latin.variable} ${devanagari.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
