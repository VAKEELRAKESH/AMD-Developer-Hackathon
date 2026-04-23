import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AMD AgentForge — AI Application Builder",
  description:
    "Autonomous multi-agent system that converts natural language into deployable full-stack applications. Optimized for AMD ROCm GPU acceleration.",
  keywords: [
    "AMD",
    "ROCm",
    "AI",
    "code generation",
    "multi-agent",
    "LangGraph",
    "vLLM",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] antialiased">
        {children}
      </body>
    </html>
  );
}
