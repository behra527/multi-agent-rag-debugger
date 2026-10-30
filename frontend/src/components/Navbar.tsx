import React from "react";
import { Activity, Bug, Database, Cpu } from "lucide-react";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  health: { status: string; llm_provider: string; database: string } | null;
  onOpenNewSession: () => void;
  productMode: boolean;
}

const PRODUCT_TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "knowledge", label: "Knowledge" },
  { id: "debug", label: "Debug" },
  { id: "evaluation", label: "Evaluation" },
  { id: "reports", label: "Reports" },
  { id: "settings", label: "Settings" },
  { id: "code-lab", label: "Code Lab" },
];

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  health,
  onOpenNewSession,
  productMode,
}) => {
  return (
    <header className="border-b border-border bg-card/80 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
            <Bug className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-foreground flex items-center space-x-2">
              <span>Multi-Agent RAG Debugger</span>
            </div>
            <p className="text-xs text-muted-foreground hidden sm:block">
              Diagnose retrieval, generation, and evaluation on your documents
            </p>
          </div>
        </div>

        <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-border text-sm font-medium">
          {PRODUCT_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                activeTab === tab.id
                  ? "bg-secondary text-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex items-center space-x-3">
        {health && (
          <div className="hidden lg:flex items-center space-x-3 text-xs bg-secondary/60 border border-border px-3 py-1.5 rounded-full">
            <span className="flex items-center space-x-1.5 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>API {health.status}</span>
            </span>
            <span className="flex items-center space-x-1 text-muted-foreground">
              <Cpu className="w-3.5 h-3.5" />
              <span className="capitalize">{health.llm_provider}</span>
            </span>
            <span className="flex items-center space-x-1 text-muted-foreground">
              <Database className="w-3.5 h-3.5" />
              <span>DB {health.database === "connected" ? "OK" : "Err"}</span>
            </span>
          </div>
        )}

        {!productMode && (
          <button
            onClick={onOpenNewSession}
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium text-xs px-4 py-2 rounded-lg transition-all shadow-sm flex items-center space-x-1.5"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>New Code Debug</span>
          </button>
        )}
      </div>
    </header>
  );
};
