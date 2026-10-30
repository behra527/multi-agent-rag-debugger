import React from "react";
import {
  FileSearch,
  Cpu,
  Database,
  Stethoscope,
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { StageTrace } from "../types";

interface WorkflowStepperProps {
  traces: StageTrace[];
  overallStatus: string;
}

const STAGES = [
  { id: "intake", label: "Issue Intake", icon: FileSearch },
  { id: "analyze", label: "Issue Analysis", icon: Cpu },
  { id: "retrieve", label: "Hybrid RAG Retrieval", icon: Database },
  { id: "root_cause", label: "Root Cause Diagnosis", icon: Stethoscope },
  { id: "generate_fix", label: "Patch Generation", icon: Wrench },
  { id: "validate", label: "Sandbox Validation", icon: CheckCircle2 },
];

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  traces,
  overallStatus,
}) => {
  const getStageTrace = (stageId: string) => {
    return traces.find((t) => t.stage === stageId || t.stage.toLowerCase() === stageId.toLowerCase());
  };

  return (
    <div className="bg-card border border-border rounded-xl p-5 shadow-sm mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Multi-Agent Execution Pipeline
          </h3>
          <p className="text-xs text-muted-foreground">
            LangGraph Supervised Workflow Trace
          </p>
        </div>
        <span
          className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
            overallStatus === "validated" || overallStatus === "completed"
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : overallStatus === "failed"
              ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
              : "bg-blue-500/10 text-blue-400 border-blue-500/20"
          }`}
        >
          Status: {overallStatus}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {STAGES.map((stage) => {
          const trace = getStageTrace(stage.id);
          const Icon = stage.icon;
          const isCompleted = trace && trace.status === "completed";
          const isFailed = trace && trace.status === "failed";
          const isRunning = trace && trace.status === "running";

          return (
            <div
              key={stage.id}
              className={`rounded-lg p-3 border text-left transition-all ${
                isCompleted
                  ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-300"
                  : isFailed
                  ? "bg-rose-950/20 border-rose-500/30 text-rose-300"
                  : isRunning
                  ? "bg-primary/10 border-primary/40 text-primary animate-pulse"
                  : "bg-secondary/40 border-border/60 text-muted-foreground"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <Icon className="w-4 h-4" />
                {isCompleted ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : isFailed ? (
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                ) : isRunning ? (
                  <Clock className="w-3.5 h-3.5 text-primary animate-spin" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-muted-foreground/30" />
                )}
              </div>
              <div className="text-xs font-semibold leading-tight mb-1 text-foreground">
                {stage.label}
              </div>
              <div className="text-[10px] text-muted-foreground flex items-center space-x-1">
                {trace?.duration_ms !== undefined ? (
                  <span>{(trace.duration_ms / 1000).toFixed(2)}s</span>
                ) : isRunning ? (
                  <span>Executing...</span>
                ) : (
                  <span>Pending</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
