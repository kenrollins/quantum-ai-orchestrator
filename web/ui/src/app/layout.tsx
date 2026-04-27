import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "quantum-ai-orchestrator",
  description: "AI-orchestrated control plane for hybrid quantum-classical workloads",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
