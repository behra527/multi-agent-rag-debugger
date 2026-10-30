import React, { useEffect, useMemo, useState } from "react";
import { GitBranch, LogOut, Moon, Plus, Search, Sparkles, Sun } from "lucide-react";
import { api, clearAuth, getAuthToken, setWorkspaceId } from "./services/api";
import { AuthScreen } from "./components/AuthScreen";
import { Badge, Button, Card, Field, Input, Textarea } from "./components/ui";
import { DiffViewer } from "./components/DiffViewer";
import { RagWorkspace } from "./components/RagWorkspace";
import { AppShell } from "./components/AppShell";

type Session = {
  id: string;
  state: string;
  title: string;
  description: string;
  repository_path: string;
  message: string;
  current_patch_revision?: string | null;
  investigation?: {
    diagnosis: string;
    root_cause: string;
    explanation: string;
    affected_files: string[];
    confidence: number;
    evidence: Array<{ source: string; content: string; start_line: number }>;
  } | null;
  proposal?: {
    summary: string;
    patch: string;
    patch_revision: string;
    affected_files: string[];
    reasoning: string;
  } | null;
  verification?: {
    passed: boolean;
    tests_run: number;
    tests_passed: number;
    tests_failed: number;
    output: string;
    remaining_blockers: string[];
  } | null;
  events: Array<{ agent: string; status: string; message: string }>;
  checkpoints?: Array<{ id: string; patch_revision: string; created_at?: string | null }>;
};

const FALLBACK_REPO = "";

function stateMeta(state: string): { label: string; tone: "ok" | "warn" | "danger" | "info" | "neutral" } {
  if (state === "AWAITING_APPROVAL") return { label: "Needs review", tone: "warn" };
  if (state === "READY_FOR_INTEGRATION") return { label: "Ready", tone: "ok" };
  if (state === "COMPLETED") return { label: "Done", tone: "ok" };
  if (state === "REJECTED" || state === "CANCELLED") return { label: state === "REJECTED" ? "Rejected" : "Cancelled", tone: "neutral" };
  if (state === "BLOCKED") return { label: "Blocked", tone: "danger" };
  if (state === "TESTING" || state === "INVESTIGATING") return { label: "Running", tone: "info" };
  return { label: state.replaceAll("_", " ").toLowerCase(), tone: "neutral" };
}

export function App() {
  const [mode, setMode] = useState<"repair" | "rag">("repair");
  const [health, setHealth] = useState<any>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [current, setCurrent] = useState<Session | null>(null);
  const [composing, setComposing] = useState(false);
  const [booted, setBooted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({
    title: "",
    description: "",
    traceback: "",
    expected_behavior: "",
    actual_behavior: "",
    repository_path: FALLBACK_REPO,
    repository_url: "",
    branch: "",
  });
  const [repos, setRepos] = useState<Array<{ name: string; path: string }>>([]);
  const [theme, setTheme] = useState(localStorage.getItem("atlas-theme") || "dark");
  const [user, setUser] = useState<{ email: string; workspace_id: string } | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sessions.filter((s) => !q || s.title.toLowerCase().includes(q) || s.state.toLowerCase().includes(q));
  }, [sessions, query]);

  const refresh = async (id?: string) => {
    const list = await api.listRepairSessions().catch(() => []);
    setSessions(list);
    if (id) setCurrent(await api.getRepairSession(id));
  };

  useEffect(() => {
    document.documentElement.classList.toggle("light", theme === "light");
    localStorage.setItem("atlas-theme", theme);
  }, [theme]);

  const bootstrapAuthedApp = async () => {
    api
      .getHealth()
      .then((value) => {
        setHealth(value);
        setApiError(null);
      })
      .catch((err) => {
        setHealth(null);
        setApiError(err instanceof Error ? err.message : String(err));
      });
    api
      .listAuthorizedRepos()
      .then((data) => {
        const items = data.items || [];
        setRepos(items);
        setForm((currentForm) => {
          if (currentForm.repository_path) return currentForm;
          const first = items[0];
          return first ? { ...currentForm, repository_path: first.path } : currentForm;
        });
      })
      .catch(() => undefined);
    const list = await api.listRepairSessions().catch(() => []);
    setSessions(list);
    if (list[0]) setCurrent(await api.getRepairSession(list[0].id).catch(() => list[0]));
    else setCurrent(null);
    setBooted(true);
  };

  useEffect(() => {
    (async () => {
      if (!getAuthToken()) {
        setAuthReady(true);
        return;
      }
      try {
        const me = await api.me();
        if (me.auth_type !== "user" || !me.email) {
          clearAuth();
          setAuthReady(true);
          return;
        }
        setWorkspaceId(me.workspace_id);
        setUser({ email: me.email, workspace_id: me.workspace_id });
        await bootstrapAuthedApp();
      } catch {
        clearAuth();
      } finally {
        setAuthReady(true);
      }
    })();
  }, []);

  const handleAuthed = async (profile: { email: string; workspace_id: string }) => {
    setUser(profile);
    setBooted(false);
    await bootstrapAuthedApp();
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      /* token may already be invalid */
    }
    clearAuth();
    setUser(null);
    setSessions([]);
    setCurrent(null);
    setComposing(false);
    setBooted(false);
  };

  if (!authReady) {
    return <div className="min-h-screen bg-background" />;
  }
  if (!user) {
    return <AuthScreen onAuthed={handleAuthed} />;
  }

  if (mode === "rag") {
    return (
      <AppShell activeTab="workspace" setActiveTab={() => undefined} health={health}>
        <button className="text-xs text-muted-foreground mb-4" onClick={() => setMode("repair")}>
          ← Back to Atlas
        </button>
        <RagWorkspace tab="workspace" onNavigate={() => undefined} />
      </AppShell>
    );
  }

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  const openNew = () => {
    setComposing(true);
    setCurrent(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="h-14 border-b border-border px-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">Atlas</div>
            <div className="text-[10px] text-muted-foreground">Code repair workspace</div>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-2 flex-1 max-w-md mx-6">
          <div className="flex-1 flex items-center gap-2 bg-secondary border border-border rounded-lg px-3 h-9">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input
              className="bg-transparent w-full text-sm outline-none"
              placeholder="Search sessions"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className={`hidden sm:inline-flex items-center gap-1.5 px-2 py-1 rounded-full ${health?.status === "ok" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${health?.status === "ok" ? "bg-emerald-400" : "bg-rose-400"}`} />
            {health?.status === "ok" ? "Connected" : "API offline"}
          </span>
          <span className="hidden md:inline text-muted-foreground truncate max-w-[160px]" title={user.email}>
            {user.email}
          </span>
          <button className="p-2 rounded-lg hover:bg-secondary" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label="Toggle theme">
            {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
          <Button variant="ghost" onClick={() => void handleLogout()}>
            <span className="inline-flex items-center gap-1.5">
              <LogOut className="w-4 h-4" /> Logout
            </span>
          </Button>
          <Button onClick={openNew}>
            <span className="inline-flex items-center gap-1.5">
              <Plus className="w-4 h-4" /> New session
            </span>
          </Button>
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-56px)]">
        <aside className="hidden lg:flex w-72 shrink-0 flex-col border-r border-border bg-sidebar">
          <div className="px-4 py-3 text-[11px] uppercase tracking-wide text-muted-foreground">Inbox</div>
          <nav className="flex-1 overflow-auto px-2 pb-4 space-y-1">
            {!filtered.length && <p className="px-2 text-sm text-muted-foreground">No sessions yet.</p>}
            {filtered.map((session) => {
              const meta = stateMeta(session.state);
              const active = current?.id === session.id && !composing;
              return (
                <button
                  key={session.id}
                  className={`w-full text-left px-3 py-2.5 rounded-lg ${active ? "bg-secondary" : "hover:bg-secondary/60"}`}
                  onClick={() =>
                    run(async () => {
                      setComposing(false);
                      setCurrent(await api.getRepairSession(session.id));
                    })
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm">{session.title}</span>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </div>
                </button>
              );
            })}
          </nav>
          <button className="px-4 py-3 text-xs text-muted-foreground border-t border-border text-left hover:bg-secondary" onClick={() => setMode("rag")}>
            Document debugger
          </button>
        </aside>

        <main className="flex-1 min-w-0 overflow-auto">
          {apiError && (
            <div className="m-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm">
              <p className="font-medium">API offline</p>
              <p className="mt-1 text-muted-foreground">{apiError}</p>
            </div>
          )}
          {error && <div className="m-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm">{error}</div>}

          {booted && !composing && !current && (
            <div className="max-w-2xl mx-auto px-6 py-24 text-center">
              <h1 className="text-3xl font-semibold tracking-tight">Fix production bugs with evidence</h1>
              <p className="text-muted-foreground mt-3 leading-7">
                Paste the error, point Atlas at a repository it can read, review the proposed patch, then approve tests on an isolated copy.
              </p>
              <div className="mt-8 flex justify-center">
                <Button onClick={openNew}>Create your first session</Button>
              </div>
            </div>
          )}

          {composing && (
            <div className="max-w-2xl mx-auto px-6 py-10">
              <p className="text-xs text-muted-foreground mb-2">New session</p>
              <h1 className="text-2xl font-semibold tracking-tight">What broke?</h1>
              <p className="text-sm text-muted-foreground mt-1 mb-6">Keep it short. Agents will inspect the repo themselves.</p>
              <div className="space-y-4">
                <Field label="Title">
                  <Input placeholder="Login accepts any password" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                </Field>
                <Field label="Description">
                  <Textarea placeholder="What you expected vs what happened" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
                </Field>
                <Field label="Traceback">
                  <Textarea className="min-h-28 font-mono text-xs" placeholder="Optional stack trace" value={form.traceback} onChange={(e) => setForm({ ...form, traceback: e.target.value })} />
                </Field>
                <div className="grid sm:grid-cols-2 gap-3">
                  <Field label="Expected">
                    <Input value={form.expected_behavior} onChange={(e) => setForm({ ...form, expected_behavior: e.target.value })} />
                  </Field>
                  <Field label="Actual">
                    <Input value={form.actual_behavior} onChange={(e) => setForm({ ...form, actual_behavior: e.target.value })} />
                  </Field>
                </div>
                <Field label="Repository">
                  <select
                    className="w-full bg-secondary border border-border rounded-xl px-3.5 py-2.5 text-sm"
                    value={form.repository_path}
                    onChange={(e) => setForm({ ...form, repository_path: e.target.value })}
                  >
                    {repos.length === 0 && <option value="">No demo repositories found</option>}
                    {repos.map((repo) => (
                      <option key={repo.path} value={repo.path}>
                        {repo.name} — {repo.path}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="GitHub URL (optional)">
                  <Input placeholder="https://github.com/org/repo" value={form.repository_url} onChange={(e) => setForm({ ...form, repository_url: e.target.value })} />
                </Field>
                <div className="flex gap-2 pt-2">
                  <Button
                    disabled={busy || !form.title.trim() || !form.description.trim()}
                    onClick={() =>
                      run(async () => {
                        const created = await api.createRepairSession({
                          ...form,
                          repository_url: form.repository_url || null,
                          branch: form.branch || null,
                        });
                        setCurrent(created);
                        setComposing(false);
                        await refresh(created.id);
                      })
                    }
                  >
                    {busy ? "Working…" : "Investigate"}
                  </Button>
                  <Button variant="ghost" onClick={() => setComposing(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}

          {!composing && current && (
            <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge tone={stateMeta(current.state).tone}>{stateMeta(current.state).label}</Badge>
                    <span className="text-xs text-muted-foreground">{current.state}</span>
                  </div>
                  <h1 className="text-2xl font-semibold tracking-tight">{current.title}</h1>
                  <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                    <GitBranch className="w-4 h-4" />
                    <span className="truncate">{current.repository_path}</span>
                  </p>
                </div>
              </div>
              {current.state === "BLOCKED" ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm">
                  <p className="font-medium">{current.message}</p>
                  {current.investigation?.explanation && (
                    <p className="mt-1 text-muted-foreground">{current.investigation.explanation}</p>
                  )}
                </div>
              ) : (
                current.message && <p className="text-sm text-muted-foreground">{current.message}</p>
              )}

              <div className="grid lg:grid-cols-[220px_1fr] gap-6">
                <Card title="Activity">
                  <ol className="space-y-3">
                    {(current.events || []).map((event, idx) => (
                      <li key={idx} className="text-sm">
                        <div className="font-medium capitalize">{event.agent.replaceAll("_", " ")}</div>
                        <div className="text-xs text-muted-foreground">{event.message}</div>
                      </li>
                    ))}
                  </ol>
                </Card>
                <div className="space-y-5">
                  {current.investigation && (
                    <Card title="Diagnosis">
                      <p className="text-[15px] leading-7">{current.investigation.diagnosis}</p>
                      <p className="text-sm text-muted-foreground mt-3">{current.investigation.root_cause}</p>
                    </Card>
                  )}
                  {current.proposal && (
                    <DiffViewer
                      patch={current.proposal.patch}
                      summary={current.proposal.summary}
                      affectedFiles={current.proposal.affected_files}
                      reasoning={current.proposal.reasoning}
                    />
                  )}
                  {current.verification && (
                    <Card title="Tests">
                      <p className="text-sm">
                        {current.verification.passed ? "Passed on the isolated candidate." : "Failed on the isolated candidate."}{" "}
                        {current.verification.tests_passed}/{current.verification.tests_run}
                      </p>
                      <pre className="mt-3 text-xs whitespace-pre-wrap max-h-56 overflow-auto text-muted-foreground">
                        {current.verification.output || (current.verification.remaining_blockers || []).join("\n")}
                      </pre>
                    </Card>
                  )}
                </div>
              </div>

              {current.state === "AWAITING_APPROVAL" && current.proposal && (
                <div className="sticky bottom-4 rounded-2xl border border-border bg-card p-4 flex flex-wrap gap-2 items-center justify-between shadow-lg">
                  <div className="text-sm">
                    Review this patch before any tests run on a copy of the repo.
                    <div className="text-xs text-muted-foreground">Revision {current.current_patch_revision}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          setCurrent(
                            await api.decideRepairSession(current.id, {
                              decision: "approved",
                              patch_revision: current.current_patch_revision || current.proposal!.patch_revision,
                            })
                          );
                          await refresh();
                        })
                      }
                    >
                      Approve
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          setCurrent(
                            await api.decideRepairSession(current.id, {
                              decision: "revision_requested",
                              patch_revision: current.current_patch_revision || "",
                              comment: "Please tighten the patch.",
                            })
                          );
                          await refresh();
                        })
                      }
                    >
                      Request changes
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          setCurrent(
                            await api.decideRepairSession(current.id, {
                              decision: "rejected",
                              patch_revision: current.current_patch_revision || "",
                            })
                          );
                          await refresh();
                        })
                      }
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              )}

              {current.state === "READY_FOR_INTEGRATION" && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      setCurrent(await api.integrateRepairSession(current.id));
                      await refresh();
                    })
                  }
                >
                  Authorize integration
                </Button>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
