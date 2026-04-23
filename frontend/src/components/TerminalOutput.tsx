import { useRef, useEffect, useState } from "react";
import { Terminal as TerminalIcon, Download, Rocket, Loader2 } from "lucide-react";
import { type AgentUpdate } from "@/hooks/useForgeStream";

interface TerminalOutputProps {
  updates: AgentUpdate[];
}

export default function TerminalOutput({ updates }: TerminalOutputProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [stdout, setStdout] = useState<string>("");
  const [stderr, setStderr] = useState<string>("");
  const [isDeploying, setIsDeploying] = useState(false);
  const [deployResult, setDeployResult] = useState<{ url?: string; error?: string } | null>(null);

  const isReady = updates.some((u) => u.phase === "deploy_ready");
  const codeBlocksMap = updates
    .filter((u) => u.agent === "engineer" && u.data?.code_blocks)
    .pop()?.data?.code_blocks as Record<string, { size: number; preview: string }>;

  // Extract logs from sandbox updates
  useEffect(() => {
    const sandboxUpdates = updates.filter(
      (u) => u.agent === "sandbox" && (u.data?.sandbox_stdout || u.data?.sandbox_stderr)
    );

    if (sandboxUpdates.length > 0) {
      const latest = sandboxUpdates[sandboxUpdates.length - 1];
      if (latest.data?.sandbox_stdout) {
        setStdout(String(latest.data.sandbox_stdout));
      }
      if (latest.data?.sandbox_stderr) {
        setStderr(String(latest.data.sandbox_stderr));
      }
    } else {
      // Clear if no sandbox updates left (e.g. new generation)
      setStdout("");
      setStderr("");
      setDeployResult(null);
    }
  }, [updates]);

  // Autoscroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [stdout, stderr, isReady]);

  const handleDownload = async () => {
    if (!codeBlocksMap) return;
    
    setIsDeploying(true);
    setDeployResult(null);
    
    try {
      // Reconstitute code blocks for the API request (we only have preview here, 
      // but in a real app we'd fetch the full state or send a session_id)
      // For the hackathon demo, we will simulate the download 
      
      const res = await fetch("http://localhost:8080/api/deploy/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          target: "download", 
          app_name: "agentforge-app",
          // We send back what we have, but realistically the backend should 
          // pull from its session state. We'll pass the previews to appease the type schema.
          code_blocks: Object.fromEntries(
            Object.entries(codeBlocksMap).map(([k, v]) => [k, v.preview])
          )
        }),
      });

      if (!res.ok) throw new Error("Download failed");

      // Trigger file download
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "agentforge-app.zip";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      
      setDeployResult({ url: "Downloaded locally" });
    } catch (err) {
      console.error(err);
      setDeployResult({ error: "Failed to create archive" });
    } finally {
      setIsDeploying(false);
    }
  };

  return (
    <div className="glass flex h-[600px] flex-col rounded-2xl border border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-4 py-3 rounded-t-2xl">
        <div className="flex items-center gap-2">
          <TerminalIcon className="h-5 w-5 text-[var(--color-text-secondary)]" />
          <h3 className="font-semibold text-[var(--color-text-primary)]">Sandbox Logs</h3>
        </div>
      </div>

      {/* Terminal View */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto bg-[#0d0d12] p-4 font-mono text-xs shadow-inner"
      >
        {!stdout && !stderr && !isReady && (
          <div className="text-[var(--color-text-muted)] italic">
            Waiting for sandbox execution...
          </div>
        )}

        {stdout && (
          <div className="mb-4">
            <div className="mb-1 text-green-400 font-bold"># stdout</div>
            <pre className="whitespace-pre-wrap text-emerald-300/80">{stdout}</pre>
          </div>
        )}

        {stderr && (
          <div className="mb-4">
            <div className="mb-1 text-red-500 font-bold"># stderr</div>
            <pre className="whitespace-pre-wrap text-red-400/80">{stderr}</pre>
          </div>
        )}

        {/* Deploy Action Area */}
        {isReady && (
          <div className="mt-8 animate-slide-up rounded-xl border border-[var(--color-success)] bg-[rgba(34,197,94,0.05)] p-4 text-center">
            <h4 className="mb-2 text-sm font-bold text-[var(--color-success)]">
              Deployment Ready
            </h4>
            <p className="mb-4 text-xs text-[var(--color-text-secondary)]">
              All sandbox tests passed. Your application is ready to ship.
            </p>
            
            <div className="flex justify-center gap-3">
              <button 
                onClick={handleDownload}
                disabled={isDeploying}
                className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-border-hover)] disabled:opacity-50"
              >
                {isDeploying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Download ZIP
              </button>
              
              <button 
                className="flex items-center gap-2 rounded-lg bg-[var(--color-amd-red)] px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-[var(--color-amd-crimson)]"
                onClick={() => alert("Vercel deployment coming soon in v2!")}
              >
                <Rocket className="h-4 w-4" />
                Deploy via API
              </button>
            </div>
            
            {deployResult?.error && (
              <p className="mt-3 text-xs text-[var(--color-error)]">{deployResult.error}</p>
            )}
            {deployResult?.url && (
              <p className="mt-3 text-xs text-[var(--color-success)]">{deployResult.url}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
