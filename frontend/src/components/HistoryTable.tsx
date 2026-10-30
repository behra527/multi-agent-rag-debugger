import React, { useState } from "react";
import { Search, Download, ExternalLink, CheckCircle2, XCircle, Clock } from "lucide-react";
import { DebuggingRunSummary } from "../types";

interface HistoryTableProps {
  runs: DebuggingRunSummary[];
  onSelectRun: (runId: string) => void;
  selectedRunId?: string;
}

export const HistoryTable: React.FC<HistoryTableProps> = ({
  runs,
  onSelectRun,
  selectedRunId,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filteredRuns = runs.filter((r) => {
    const matchesSearch =
      r.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.run_id.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === "all" || r.status.toLowerCase() === statusFilter.toLowerCase();

    return matchesSearch && matchesStatus;
  });

  const handleDownload = (run: DebuggingRunSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    const blob = new Blob([JSON.stringify(run, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `debugging-run-${run.run_id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden mb-6">
      <div className="p-4 border-b border-border bg-secondary/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Debugging Session History
          </h3>
          <p className="text-xs text-muted-foreground">
            Auditable records of previous analyses, patches, and validation results
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <div className="relative">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search runs..."
              className="bg-background border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary w-44"
            />
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-2" />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-background border border-border rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Statuses</option>
            <option value="validated">Validated</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-border bg-secondary/20 text-muted-foreground uppercase text-[10px] tracking-wider font-semibold">
              <th className="py-2.5 px-4">Run ID / Date</th>
              <th className="py-2.5 px-4">Issue Title</th>
              <th className="py-2.5 px-4">Repository</th>
              <th className="py-2.5 px-4">Duration</th>
              <th className="py-2.5 px-4">Validation</th>
              <th className="py-2.5 px-4">Approval</th>
              <th className="py-2.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredRuns.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-muted-foreground text-xs">
                  No debugging sessions found. Start a new session above!
                </td>
              </tr>
            ) : (
              filteredRuns.map((r) => {
                const isSelected = selectedRunId === r.run_id;
                const isSuccess = r.status === "validated" || r.status === "completed";

                return (
                  <tr
                    key={r.run_id}
                    onClick={() => onSelectRun(r.run_id)}
                    className={`cursor-pointer transition-colors hover:bg-secondary/40 ${
                      isSelected ? "bg-primary/10 font-medium" : ""
                    }`}
                  >
                    <td className="py-3 px-4 font-mono text-[11px] text-foreground">
                      <div>{r.run_id.slice(0, 8)}...</div>
                      <div className="text-[10px] text-muted-foreground">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}
                      </div>
                    </td>

                    <td className="py-3 px-4 font-medium text-foreground max-w-xs truncate">
                      {r.title}
                    </td>

                    <td className="py-3 px-4 text-muted-foreground font-mono text-[11px] max-w-xs truncate">
                      {r.repository_path}
                    </td>

                    <td className="py-3 px-4 text-muted-foreground">
                      {r.duration_ms !== undefined ? `${(r.duration_ms / 1000).toFixed(1)}s` : "—"}
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium border ${
                          isSuccess
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        }`}
                      >
                        {isSuccess ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : (
                          <XCircle className="w-3 h-3" />
                        )}
                        <span className="capitalize">{r.status}</span>
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`inline-block text-[10px] uppercase font-semibold px-2 py-0.5 rounded border ${
                          r.approval_status === "approved"
                            ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                            : r.approval_status === "rejected"
                            ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                            : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {r.approval_status}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => handleDownload(r, e)}
                        title="Download JSON Report"
                        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
