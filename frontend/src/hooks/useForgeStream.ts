"use client";

import { useState, useCallback, useRef } from "react";

export interface AgentUpdate {
  type: "session_start" | "agent_update" | "complete" | "error";
  agent?: string;
  phase?: string;
  data?: Record<string, unknown>;
  session_id?: string;
  message?: string;
}

interface CodeBlocksMap {
  [filename: string]: {
    size: number;
    preview: string;
  };
}

export function useForgeStream() {
  const [updates, setUpdates] = useState<AgentUpdate[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentPhase, setCurrentPhase] = useState<string>("idle");
  const [codeBlocks, setCodeBlocks] = useState<CodeBlocksMap>({});
  const [gpuTelemetry, setGpuTelemetry] = useState<Record<string, unknown> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const startGeneration = useCallback((prompt: string) => {
    setIsRunning(true);
    setUpdates([]);
    setCodeBlocks({});
    setGpuTelemetry(null);
    setCurrentPhase("intake");

    const wsUrl =
      process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8080";
    const ws = new WebSocket(`${wsUrl}/ws/generate`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ prompt }));
    };

    ws.onmessage = (event) => {
      try {
        const update: AgentUpdate = JSON.parse(event.data);
        setUpdates((prev) => [...prev, update]);

        if (update.phase) {
          setCurrentPhase(update.phase);
        }

        if (update.data?.gpu_telemetry) {
          setGpuTelemetry(update.data.gpu_telemetry as Record<string, unknown>);
        }

        // Extract code blocks from engineer updates
        if (
          update.agent === "engineer" &&
          update.data?.code_blocks &&
          typeof update.data.code_blocks === "object"
        ) {
          setCodeBlocks(update.data.code_blocks as CodeBlocksMap);
        }

        if (update.type === "complete" || update.type === "error") {
          setIsRunning(false);
          ws.close();
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      setIsRunning(false);
      setCurrentPhase("failed");
      setUpdates((prev) => [
        ...prev,
        {
          type: "error",
          message: "WebSocket connection failed. Is the backend running?",
        },
      ]);
    };

    ws.onclose = () => {
      setIsRunning(false);
    };
  }, []);

  const cancel = useCallback(() => {
    wsRef.current?.close();
    setIsRunning(false);
    setCurrentPhase("idle");
  }, []);

  return {
    updates,
    isRunning,
    currentPhase,
    codeBlocks,
    gpuTelemetry,
    startGeneration,
    cancel,
  };
}
