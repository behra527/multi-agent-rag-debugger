import React from "react";
import { Clock3, FolderOpen, Settings, Sparkles } from "lucide-react";

const NAV = [
  { id: "workspace", label: "Workspace", icon: FolderOpen },
  { id: "history", label: "History", icon: Clock3 },
  { id: "account", label: "Account", icon: Settings },
];

export function AppShell({
  activeTab,
  setActiveTab,
  health,
  busy,
  children,
}: {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  health: { status: string; llm_provider: string; database: string } | null;
  busy?: boolean;
  children: React.ReactNode;
}) {
  const current = ["workspace", "history", "account", "code-lab"].includes(activeTab)
    ? activeTab
    : "workspace";

  return (
    <div className="min-h-screen flex text-foreground">
      <aside className="hidden md:flex w-[232px] shrink-0 flex-col border-r border-border/80 bg-[#0b1629]/90">
        <div className="px-5 py-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="font-semibold tracking-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
                RAG Debugger
              </div>
              <div className="text-[11px] text-muted-foreground">Ask your docs. See why.</div>
            </div>
          </div>
        </div>
        <nav className="px-3 flex-1 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = current === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="p-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${health?.status === "ok" ? "bg-ok" : "bg-destructive"}`} />
            {health?.status === "ok" ? "Online" : "Backend offline — start the API"}
          </div>
          {busy && <div className="mt-1 text-primary">Working…</div>}
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden border-b border-border px-4 py-3 flex gap-2 overflow-x-auto">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`text-xs px-3 py-1.5 rounded-full whitespace-nowrap ${
                current === item.id ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </header>
        <main className="flex-1 p-5 lg:p-10 max-w-4xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
