import { useState, KeyboardEvent } from "react";
import { Send, XCircle, Sparkles } from "lucide-react";

interface PromptInputProps {
  onSubmit: (prompt: string) => void;
  onCancel: () => void;
  isRunning: boolean;
}

export default function PromptInput({ onSubmit, onCancel, isRunning }: PromptInputProps) {
  const [prompt, setPrompt] = useState("");

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (prompt.trim() && !isRunning) {
        onSubmit(prompt);
      }
    }
  };

  return (
    <div className="glass relative rounded-2xl border border-[var(--color-border)] p-2 transition-all focus-within:border-[var(--color-amd-red)] focus-within:shadow-[0_0_20px_var(--color-amd-red-glow)]">
      <div className="relative flex items-center">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isRunning}
          placeholder="Describe the application you want to build... (e.g. 'A real-time chat app with user auth')"
          className="min-h-[60px] w-full resize-none bg-transparent px-4 py-3 text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none disabled:opacity-50"
          rows={1}
        />
        
        <div className="absolute right-2 top-1/2 -translate-y-1/2">
          {isRunning ? (
            <button
              onClick={onCancel}
              className="flex items-center gap-2 rounded-xl bg-[var(--color-bg-tertiary)] px-4 py-2 text-sm font-medium text-[var(--color-error)] transition-colors hover:bg-[var(--color-bg-elevated)]"
            >
              <XCircle className="h-4 w-4" />
              Cancel
            </button>
          ) : (
            <button
              onClick={() => prompt.trim() && onSubmit(prompt)}
              disabled={!prompt.trim()}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--color-amd-red)] to-[var(--color-amd-crimson)] px-5 py-2.5 text-sm font-bold text-white shadow-lg transition-all hover:scale-[1.02] hover:shadow-[0_0_15px_var(--color-amd-red-glow)] disabled:pointer-events-none disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              Generate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
