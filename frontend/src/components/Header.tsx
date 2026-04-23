import { useState, useEffect } from "react";
import { Server, Activity, Cpu, Code2, Play } from "lucide-react";

interface InferenceInfo {
  status: string;
  version: string;
  inference_backend: {
    name: string;
    description: string;
    features: string[];
  };
  sandbox_enabled: boolean;
}

export default function Header({ currentPhase }: { currentPhase: string }) {
  const [info, setInfo] = useState<InferenceInfo | null>(null);

  useEffect(() => {
    // Fetch backend info
    const fetchInfo = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
        const res = await fetch(`${apiUrl}/api/health`);
        const data = await res.json();
        setInfo(data);
      } catch (err) {
        console.error("Failed to fetch backend info");
      }
    };
    fetchInfo();
  }, []);

  return (
    <header className="glass sticky top-0 z-50 flex items-center justify-between border-b border-[var(--color-border)] px-6 py-4">
      {/* ── Logo & Title ─────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--color-amd-red)] to-[var(--color-amd-crimson)] shadow-[0_0_15px_var(--color-amd-red-glow)]">
          <Code2 className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)]">
            AMD AgentForge
          </h1>
          <p className="text-xs font-medium text-[var(--color-text-muted)]">
            Autonomous Multi-Agent AI
          </p>
        </div>
      </div>

      {/* ── Status Indicators ────────────────────────────── */}
      <div className="flex items-center gap-4">
        {/* Phase Indicator */}
        <div className="flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm">
          <Activity
            className={`h-4 w-4 ${
              currentPhase !== "idle" && currentPhase !== "failed" && currentPhase !== "deployed"
                ? "animate-pulse text-[var(--color-amd-red)]"
                : "text-[var(--color-text-muted)]"
            }`}
          />
          <span className="font-mono text-xs uppercase tracking-wider text-[var(--color-text-secondary)]">
            {currentPhase}
          </span>
        </div>

        {/* Backend Info */}
        <div className="hidden items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm sm:flex">
          <Cpu
            className={`h-4 w-4 ${
              info?.inference_backend.name.includes("ROCm")
                ? "text-[var(--color-amd-red)]"
                : "text-green-500"
            }`}
          />
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">
            {info ? info.inference_backend.name : "Connecting..."}
          </span>
        </div>

         {/* Sandbox Status */}
         <div className="hidden items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-3 py-1.5 text-sm sm:flex">
          <Play
            className={`h-4 w-4 ${
              info?.sandbox_enabled
                ? "text-purple-500"
                : "text-[var(--color-text-muted)]"
            }`}
          />
          <span className="text-xs font-medium text-[var(--color-text-secondary)]">
            Sandbox {info?.sandbox_enabled ? "On" : "Off"}
          </span>
        </div>
      </div>
    </header>
  );
}
