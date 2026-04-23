import { Check, Loader2 } from "lucide-react";

interface PipelineProgressProps {
  currentPhase: string;
}

const PHASES = [
  { id: "intake", label: "Prompt" },
  { id: "architecting", label: "Architect" },
  { id: "engineering", label: "Engineer" },
  { id: "sandbox_testing", label: "Sandbox" },
  { id: "deploy_ready", label: "Ready" },
];

export default function PipelineProgress({ currentPhase }: PipelineProgressProps) {
  // Determine current index. Handle reviewing/debugging as part of testing.
  const currentIndex = (() => {
    switch (currentPhase) {
      case "idle": return -1;
      case "intake": return 0;
      case "architecting": return 1;
      case "engineering": return 2;
      case "sandbox_testing":
      case "reviewing":
      case "debugging":
        return 3;
      case "deploy_ready":
      case "deployed":
        return 4;
      default: return -1; // failed or unknown
    }
  })();

  const isFailed = currentPhase === "failed";

  return (
    <div className="glass rounded-2xl border border-[var(--color-border)] p-4">
      <div className="relative flex w-full items-center justify-between">
        {/* Background Line */}
        <div className="absolute left-0 top-1/2 h-[2px] w-full -translate-y-1/2 bg-[var(--color-border)] opacity-50" />
        
        {/* Active Line */}
        <div 
          className="absolute left-0 top-1/2 h-[2px] -translate-y-1/2 transition-all duration-500 ease-in-out"
          style={{ 
            width: `${Math.max(0, (currentIndex / (PHASES.length - 1)) * 100)}%`,
            background: isFailed 
              ? "var(--color-error)" 
              : "linear-gradient(90deg, var(--color-amd-crimson), var(--color-amd-red))"
          }}
        />

        {/* Nodes */}
        {PHASES.map((phase, idx) => {
          const isCompleted = currentIndex > idx;
          const isActive = currentIndex === idx;
          const isError = isFailed && isActive; // Mark current node as error if failed

          return (
            <div key={phase.id} className="relative z-10 flex flex-col items-center gap-2">
              <div 
                className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                  isCompleted
                    ? "border-[var(--color-success)] bg-[var(--color-success)] text-white shadow-[0_0_10px_rgba(34,197,94,0.4)]"
                    : isError
                    ? "border-[var(--color-error)] bg-[var(--color-error)] text-white"
                    : isActive
                    ? "border-[var(--color-amd-red)] bg-[var(--color-bg-primary)] shadow-[0_0_10px_var(--color-amd-red-glow)]"
                    : "border-[var(--color-border)] bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]"
                }`}
              >
                {isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin text-[var(--color-amd-red)]" />
                ) : (
                  <span className="text-xs font-medium">{idx + 1}</span>
                )}
              </div>
              <span 
                className={`absolute -bottom-6 text-xs font-medium tracking-wide ${
                  isActive || isCompleted 
                    ? "text-[var(--color-text-primary)]" 
                    : "text-[var(--color-text-muted)]"
                }`}
              >
                {phase.label}
              </span>
            </div>
          );
        })}
      </div>
      {/* Spacer for bottom labels */}
      <div className="h-6" />
    </div>
  );
}
