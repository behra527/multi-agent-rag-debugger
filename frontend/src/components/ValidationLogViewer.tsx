import React from "react";
import { Terminal, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { ValidationResult } from "../types";

interface ValidationLogViewerProps {
  validation?: ValidationResult;
}

export const ValidationLogViewer: React.FC<ValidationLogViewerProps> = ({
  validation,
}) => {
  if (!validation) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 text-center text-muted-foreground text-sm mb-6">
        No validation results recorded.
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-3.5 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <Terminal className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground">
            Isolated Sandbox Test Results
          </span>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <span className="flex items-center space-x-1 text-emerald-400 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{validation.tests_passed} Passed</span>
          </span>
          {validation.tests_failed > 0 && (
            <span className="flex items-center space-x-1 text-rose-400 font-medium">
              <XCircle className="w-3.5 h-3.5" />
              <span>{validation.tests_failed} Failed</span>
            </span>
          )}
          <span
            className={`px-2 py-0.5 rounded font-mono text-[11px] font-semibold uppercase ${
              validation.passed
                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
            }`}
          >
            {validation.passed ? "PASSED" : "FAILED"}
          </span>
        </div>
      </div>

      {validation.errors && validation.errors.length > 0 && (
        <div className="p-4 bg-rose-950/20 border-b border-rose-500/20 text-rose-300 text-xs">
          <div className="font-semibold flex items-center space-x-1.5 mb-1 text-rose-400">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Validation Errors:</span>
          </div>
          <ul className="list-disc list-inside space-y-0.5 font-mono text-[11px]">
            {validation.errors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-[#0c1017] p-4 text-[#8b949e] font-mono text-xs overflow-x-auto max-h-[320px]">
        {validation.output ? (
          <pre className="whitespace-pre text-[#c9d1d9]">{validation.output}</pre>
        ) : (
          <div className="text-muted-foreground italic">No stdout/stderr output captured.</div>
        )}
      </div>
    </div>
  );
};
