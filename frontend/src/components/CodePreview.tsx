import { useState } from "react";
import Editor from "@monaco-editor/react";
import { Code, FileJson, FileType2 } from "lucide-react";

interface CodeBlocksMap {
  [filename: string]: {
    size: number;
    preview: string;
  };
}

interface CodePreviewProps {
  codeBlocks: CodeBlocksMap;
}

export default function CodePreview({ codeBlocks }: CodePreviewProps) {
  const files = Object.keys(codeBlocks).sort();
  const [selectedFile, setSelectedFile] = useState<string | null>(
    files.length > 0 ? files[0] : null
  );

  // Auto-select first file when available
  if (files.length > 0 && !selectedFile) {
    setSelectedFile(files[0]);
  }

  const getLanguage = (filename: string) => {
    const ext = filename.split(".").pop();
    switch (ext) {
      case "py":
        return "python";
      case "js":
      case "jsx":
        return "javascript";
      case "ts":
      case "tsx":
        return "typescript";
      case "json":
        return "json";
      case "css":
        return "css";
      case "html":
        return "html";
      case "md":
        return "markdown";
      default:
        return "plaintext";
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split(".").pop();
    if (ext === "py" || ext === "js" || ext === "ts" || ext === "tsx") {
      return <Code className="h-4 w-4" />;
    }
    if (ext === "json") return <FileJson className="h-4 w-4" />;
    return <FileType2 className="h-4 w-4" />;
  };

  return (
    <div className="glass flex h-[600px] flex-col rounded-2xl border border-[var(--color-border)] overflow-hidden">
      {/* ── File Tabs ────────────────────────────────────── */}
      <div className="flex border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-x-auto no-scrollbar">
        {files.length === 0 ? (
          <div className="px-4 py-3 text-sm font-medium text-[var(--color-text-muted)]">
            No files generated yet
          </div>
        ) : (
          files.map((file) => (
            <button
              key={file}
              onClick={() => setSelectedFile(file)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                selectedFile === file
                  ? "border-[var(--color-amd-red)] text-[var(--color-text-primary)] bg-[var(--color-bg-tertiary)]"
                  : "border-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              {getFileIcon(file)}
              {file.split("/").pop()} {/* Just show filename, not full path */}
            </button>
          ))
        )}
      </div>

      {/* ── Editor Area ──────────────────────────────────── */}
      <div className="flex-1 bg-[#1e1e1e]">
        {selectedFile ? (
          <Editor
            height="100%"
            language={getLanguage(selectedFile)}
            theme="vs-dark"
            value={codeBlocks[selectedFile]?.preview || "// Loading preview..."}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Menlo', monospace",
              padding: { top: 16 },
              scrollBeyondLastLine: false,
              wordWrap: "on",
            }}
            loading={
              <div className="flex h-full items-center justify-center text-[var(--color-text-muted)]">
                Loading editor...
              </div>
            }
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-[var(--color-text-muted)]">
            Awaiting Engineer Agent...
          </div>
        )}
      </div>
    </div>
  );
}
