import React from "react";
import { FileCode, Sparkles, Hash } from "lucide-react";
import { Evidence } from "../types";

interface EvidenceViewerProps {
  evidence: Evidence[];
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ evidence }) => {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 text-center text-muted-foreground text-sm mb-6">
        No code evidence retrieved for this run.
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-3.5 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground">
            Ranked Repository Evidence ({evidence.length} Chunks)
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          Grounded RAG retrieval
        </span>
      </div>

      <div className="divide-y divide-border">
        {evidence.map((item, idx) => (
          <div key={idx} className="p-4 bg-card hover:bg-secondary/10 transition-colors">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2 text-xs">
              <div className="flex items-center space-x-2 font-mono text-foreground font-medium">
                <FileCode className="w-3.5 h-3.5 text-primary" />
                <span>{item.source}</span>
                <span className="text-muted-foreground font-sans">
                  Lines {item.start_line}–{item.end_line}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] px-2 py-0.5 rounded bg-secondary text-muted-foreground border border-border font-mono">
                  {item.language}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 font-mono font-medium">
                  Score: {(item.score * 100).toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="font-mono text-xs bg-[#0d1117] text-[#c9d1d9] p-3 rounded-lg overflow-x-auto border border-border/40">
              <pre className="whitespace-pre">{item.content}</pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
