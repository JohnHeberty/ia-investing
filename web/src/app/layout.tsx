import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";
import { TelemetryProvider } from "@/components/telemetry-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "IA Investing OS", template: "%s · IA Investing OS" },
  description: "Estação institucional de pesquisa, risco e carteiras-modelo",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body>
        <Providers>
          <TelemetryProvider>
            <AppShell>{children}</AppShell>
          </TelemetryProvider>
        </Providers>
      </body>
    </html>
  );
}
