import React, { useState } from "react";
import { Copy, Check, FileCode, GitCommit } from "lucide-react";

interface DiffViewerProps {
  patch: string;
  summary?: string;
  affectedFiles?: string[];
  reasoning?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  patch,
  summary,
  affectedFiles = [],
  reasoning,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(patch);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!patch || !patch.trim()) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 text-center text-muted-foreground text-sm">
        No patch generated for this run.
      </div>
    );
  }

  const lines = patch.split("\n");

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-3.5 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <GitCommit className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground">
            Proposed Unified Diff Patch
          </span>
          {affectedFiles.length > 0 && (
            <span className="text-xs bg-secondary text-muted-foreground px-2 py-0.5 rounded border border-border">
              {affectedFiles.join(", ")}
            </span>
          )}
        </div>

        <button
          onClick={handleCopy}
          className="text-xs flex items-center space-x-1.5 px-2.5 py-1 rounded bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Copied" : "Copy Diff"}</span>
        </button>
      </div>

      {summary && (
        <div className="px-5 py-3 bg-card border-b border-border text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Summary: </span>
          {summary}
          {reasoning && (
            <div className="mt-1">
              <span className="font-semibold text-foreground">Rationale: </span>
              {reasoning}
            </div>
          )}
        </div>
      )}

      <div className="font-mono text-xs overflow-x-auto bg-[#0d1117] text-[#c9d1d9] p-4 max-h-[480px]">
        {lines.map((line, idx) => {
          let lineClass = "text-[#8b949e]"; // default context
          let bgClass = "";

          if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff --git")) {
            lineClass = "text-[#58a6ff] font-semibold";
          } else if (line.startsWith("@@")) {
            lineClass = "text-[#bc8cff]";
            bgClass = "bg-[#1f1d2e]/60";
          } else if (line.startsWith("+")) {
            lineClass = "text-[#7ee787]";
            bgClass = "bg-[#238636]/15";
          } else if (line.startsWith("-")) {
            lineClass = "text-[#ffa198]";
            bgClass = "bg-[#da3633]/15";
          }

          return (
            <div
              key={idx}
              className={`flex items-start px-2 py-0.5 rounded-sm ${bgClass}`}
            >
              <span className="w-8 select-none text-[10px] text-[#484f58] text-right pr-3">
                {idx + 1}
              </span>
              <span className={`whitespace-pre flex-1 ${lineClass}`}>{line}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
