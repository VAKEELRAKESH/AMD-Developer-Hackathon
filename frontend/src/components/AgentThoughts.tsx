import { motion, AnimatePresence } from "framer-motion";
import { type AgentUpdate } from "@/hooks/useForgeStream";
import { BrainCircuit, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

const AGENT_COLORS: Record<string, string> = {
  architect: "var(--color-agent-architect)",
  engineer: "var(--color-agent-engineer)",
  reviewer: "var(--color-agent-reviewer)",
  sandbox: "var(--color-agent-sandbox)",
  system: "var(--color-text-muted)",
};

interface AgentThoughtsProps {
  updates: AgentUpdate[];
}

export default function AgentThoughts({ updates }: AgentThoughtsProps) {
  // Filter for text updates and errors
  const messages = updates.filter(
    (u) =>
      u.type === "error" ||
      (u.type === "agent_update" && u.data?.messages)
  );

  return (
    <div className="glass flex h-[600px] flex-col rounded-2xl border border-[var(--color-border)]">
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-4 py-3 rounded-t-2xl">
        <BrainCircuit className="h-5 w-5 text-[var(--color-amd-red)]" />
        <h3 className="font-semibold text-[var(--color-text-primary)]">Agent Thoughts</h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((u, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 text-sm"
            >
              {/* Agent Icon / Color Indicator */}
              <div className="mt-1 flex-shrink-0">
                {u.type === "error" ? (
                  <AlertCircle className="h-4 w-4 text-[var(--color-error)]" />
                ) : u.phase === "deploy_ready" ? (
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
                ) : u.phase === "debugging" ? (
                  <RefreshCw className="h-4 w-4 animate-spin text-[var(--color-agent-reviewer)]" />
                ) : (
                  <div
                    className="h-2.5 w-2.5 rounded-full mt-1"
                    style={{ backgroundColor: AGENT_COLORS[u.agent || "system"] || "gray" }}
                  />
                )}
              </div>

              {/* Message Content */}
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className="font-semibold font-mono text-xs uppercase tracking-wider"
                    style={{ color: AGENT_COLORS[u.agent || "system"] || "gray" }}
                  >
                    {u.agent || "SYSTEM"}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)] uppercase">
                    {u.phase}
                  </span>
                </div>
                
                {u.type === "error" ? (
                  <p className="text-[var(--color-error)]">{u.message}</p>
                ) : (
                  <div className="text-[var(--color-text-secondary)] whitespace-pre-wrap leading-relaxed">
                    {/* Render messages from the LLM */}
                     {(u.data?.messages as Array<{role: string, content: string}>)?.map((m, i) => (
                        <div key={i} className={m.role === 'system' ? 'opacity-70 text-xs mt-1 border-l-2 border-slate-700 pl-2' : ''}>
                          {m.content}
                        </div>
                     ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-[var(--color-text-muted)] text-sm italic">
            Waiting for agent activity...
          </div>
        )}
        
        {/* Autoscroll anchor */}
        <div className="h-4" />
      </div>
    </div>
  );
}
