"use client";

import { useState } from "react";
import Header from "@/components/Header";
import PromptInput from "@/components/PromptInput";
import AgentThoughts from "@/components/AgentThoughts";
import CodePreview from "@/components/CodePreview";
import PipelineProgress from "@/components/PipelineProgress";
import TerminalOutput from "@/components/TerminalOutput";
import { useForgeStream, type AgentUpdate } from "@/hooks/useForgeStream";

export default function Home() {
  const {
    updates,
    isRunning,
    currentPhase,
    codeBlocks,
    startGeneration,
    cancel,
  } = useForgeStream();

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)] bg-grid">
      {/* ── Background Glow Effects ──────────────────────── */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-[var(--color-amd-red)] opacity-[0.03] blur-[120px]" />
        <div className="absolute -bottom-48 -right-48 h-[500px] w-[500px] rounded-full bg-[var(--color-agent-architect)] opacity-[0.03] blur-[150px]" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header currentPhase={currentPhase} />

        <main className="flex flex-1 flex-col gap-6 p-6 pt-4">
          {/* ── Prompt Input ────────────────────────────────── */}
          <PromptInput
            onSubmit={startGeneration}
            onCancel={cancel}
            isRunning={isRunning}
          />

          {/* ── Pipeline Progress ───────────────────────────── */}
          {(isRunning || updates.length > 0) && (
            <PipelineProgress currentPhase={currentPhase} />
          )}

          {/* ── Main Content Grid ───────────────────────────── */}
          {(isRunning || updates.length > 0) && (
            <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-12">
              {/* Left Column: Agent Thoughts */}
              <div className="lg:col-span-3">
                <AgentThoughts updates={updates} />
              </div>

              {/* Center Column: Code Preview */}
              <div className="lg:col-span-6">
                <CodePreview codeBlocks={codeBlocks} />
              </div>

              {/* Right Column: Terminal */}
              <div className="lg:col-span-3">
                <TerminalOutput updates={updates} />
              </div>
            </div>
          )}

          {/* ── Empty State ─────────────────────────────────── */}
          {!isRunning && updates.length === 0 && <EmptyState />}
        </main>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center py-20">
      <div className="relative mb-8">
        <div className="absolute inset-0 animate-pulse-glow rounded-2xl" />
        <div className="relative flex h-24 w-24 items-center justify-center rounded-2xl bg-gradient-to-br from-[var(--color-amd-red)] to-[var(--color-amd-crimson)]">
          <svg
            className="h-12 w-12 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
            />
          </svg>
        </div>
      </div>

      <h2 className="mb-3 text-2xl font-bold text-[var(--color-text-primary)]">
        Describe your application
      </h2>
      <p className="max-w-md text-center text-[var(--color-text-secondary)]">
        Type a natural language description above and watch three AI agents
        design, build, and debug your full-stack app in real-time.
      </p>

      {/* Example prompts */}
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        {[
          "Build a task management app with auth",
          "Create a URL shortener with analytics",
          "Make a real-time chat app with rooms",
        ].map((prompt) => (
          <button
            key={prompt}
            className="glass glass-hover rounded-full px-4 py-2 text-sm text-[var(--color-text-secondary)] transition-all duration-200 hover:text-[var(--color-text-primary)]"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
