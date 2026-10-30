import React from "react";
import { Activity, CheckCircle2, XCircle, Clock, ShieldCheck } from "lucide-react";
import { OperationalMetrics } from "../types";

interface MetricCardsProps {
  metrics: OperationalMetrics | null;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between text-muted-foreground text-xs font-medium mb-1">
          <span>Total Debugging Runs</span>
          <Activity className="w-4 h-4 text-primary" />
        </div>
        <div className="text-2xl font-bold tracking-tight text-foreground">
          {metrics ? metrics.total_runs : "—"}
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          {metrics ? `${metrics.completed_runs} validated • ${metrics.failed_runs} failed` : "Loading..."}
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between text-muted-foreground text-xs font-medium mb-1">
          <span>Validation Success Rate</span>
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-bold tracking-tight text-foreground">
          {metrics ? `${metrics.success_rate}%` : "—"}
        </div>
        <div className="text-xs text-emerald-500/90 mt-1 font-medium">
          Verified with real test suites
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between text-muted-foreground text-xs font-medium mb-1">
          <span>Approved Patches</span>
          <ShieldCheck className="w-4 h-4 text-blue-400" />
        </div>
        <div className="text-2xl font-bold tracking-tight text-foreground">
          {metrics ? metrics.approved_fixes : "—"}
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          Human-in-the-loop reviewed
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between text-muted-foreground text-xs font-medium mb-1">
          <span>Avg Stage Duration</span>
          <Clock className="w-4 h-4 text-amber-400" />
        </div>
        <div className="text-2xl font-bold tracking-tight text-foreground">
          {metrics && metrics.avg_duration_ms > 0
            ? `${(metrics.avg_duration_ms / 1000).toFixed(1)}s`
            : "—"}
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          Per automated stage execution
        </div>
      </div>
    </div>
  );
};
