import React, { useEffect, useState } from "react";
import { api, getWorkspaceId, setAuthToken, setWorkspaceId } from "../services/api";
import { DebugReport, DebugSessionSummary, KnowledgeBase } from "../types";
import { Badge, Button, Card, EmptyState, Field, Input, severityTone } from "./ui";

export function RagWorkspace({
  tab,
  onNavigate,
}: {
  tab: string;
  onNavigate: (tab: string) => void;
}) {
  const view = ["history", "account"].includes(tab) ? tab : "workspace";
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null);
  const [sessions, setSessions] = useState<DebugSessionSummary[]>([]);
  const [report, setReport] = useState<DebugReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"signin" | "register">("signin");
  const [me, setMe] = useState<Record<string, unknown> | null>(null);
  const [workspace, setWorkspace] = useState(getWorkspaceId());

  const docs = selectedKb?.documents || [];
  const ready = docs.some((doc) => doc.status === "indexed");

  const load = async () => {
    try {
      const [bases, sess, who] = await Promise.all([
        api.listKnowledgeBases().catch(() => []),
        api.listDebugSessions().catch(() => []),
        api.me().catch(() => null),
      ]);
      setMe(who);
      setKbs(bases);
      setSessions(sess);
      if (bases.length) {
        const currentId = selectedKb?.id;
        const next = bases.find((kb) => kb.id === currentId) || bases[0];
        setSelectedKb(await api.getKnowledgeBase(next.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your workspace.");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  const run = async (fn: () => Promise<void>, fallback: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : fallback);
    } finally {
      setBusy(false);
    }
  };

  const ensureLibrary = async () => {
    if (selectedKb) return selectedKb;
    if (kbs[0]) {
      const kb = await api.getKnowledgeBase(kbs[0].id);
      setSelectedKb(kb);
      return kb;
    }
    const created = await api.createKnowledgeBase({ name: "My documents", embedding_provider: "hash" });
    const kb = await api.getKnowledgeBase(created.id);
    setSelectedKb(kb);
    return kb;
  };

  const onAsk = () => {
    if (!query.trim()) {
      setError("Type a question first.");
      return;
    }
    if (!ready) {
      setError("Add a document first, or tap Try sample.");
      return;
    }
    run(async () => {
      const result = await api.createDebugSession({
        knowledge_base_id: selectedKb!.id,
        query: query.trim(),
        config: { retrieval_mode: "hybrid", generate_answer: true, top_k: 5 },
      });
      setReport(result.report);
      await load();
    }, "Could not answer from your documents.");
  };

  return (
    <div className="space-y-6">
      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-sm px-4 py-3 rounded-2xl flex justify-between gap-3">
          <span>{error}</span>
          <button className="text-xs text-destructive" onClick={() => setError(null)}>
            Close
          </button>
        </div>
      )}

      {view === "workspace" && (
        <>
          <div>
            <p className="text-xs text-muted-foreground mb-1">How to use</p>
            <h1 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
              {ready ? "Ask your documents" : "Start with a document"}
            </h1>
            <p className="text-muted-foreground mt-2 max-w-xl">
              {ready
                ? "Type a question. You will get an answer, the source text, and any problems in the pipeline."
                : "Upload a PDF, Word, or text file. Or try the built-in sample — no setup needed."}
            </p>
          </div>

          <ol className="grid grid-cols-3 gap-2 text-xs">
            {[
              ["1", "Add files", ready],
              ["2", "Ask a question", Boolean(report)],
              ["3", "Read the result", Boolean(report)],
            ].map(([n, label, done]) => (
              <li
                key={String(n)}
                className={`rounded-2xl border px-3 py-2 ${done ? "border-primary/40 bg-primary/10" : "border-border"}`}
              >
                <span className="text-muted-foreground">{n}</span> {label}
              </li>
            ))}
          </ol>

          <Card title="Your files">
            {!docs.length ? (
              <EmptyState
                title="No files yet"
                body="Use the sample policy, or upload your own file. Then ask a question."
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    <Button
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          const sample = await api.loadSample();
                          setSelectedKb(await api.getKnowledgeBase(sample.knowledge_base_id));
                          setQuery("When are refunds issued?");
                          await load();
                        }, "Could not load the sample.")
                      }
                    >
                      Try sample
                    </Button>
                    <label className="inline-flex">
                      <span className="text-sm font-medium px-4 py-2.5 rounded-xl border border-border bg-secondary/50 cursor-pointer">
                        Upload file
                      </span>
                      <input
                        type="file"
                        className="hidden"
                        accept=".txt,.md,.markdown,.pdf,.docx,.json"
                        onChange={(event) =>
                          run(async () => {
                            const file = event.target.files?.[0];
                            if (!file) return;
                            const kb = await ensureLibrary();
                            await api.uploadDocument(kb.id, file);
                            setSelectedKb(await api.getKnowledgeBase(kb.id));
                            await load();
                          }, "Upload failed.")
                        }
                      />
                    </label>
                  </div>
                }
              />
            ) : (
              <div className="space-y-3">
                <ul className="divide-y divide-border">
                  {docs.map((doc) => (
                    <li key={doc.id} className="py-2 flex items-center justify-between gap-3 text-sm">
                      <span className="truncate">{doc.filename}</span>
                      <Badge tone={doc.status === "indexed" ? "ok" : doc.status === "failed" ? "danger" : "warn"}>
                        {doc.status === "indexed" ? "ready" : doc.status}
                      </Badge>
                    </li>
                  ))}
                </ul>
                <label className="inline-flex">
                  <span className="text-sm font-medium px-4 py-2.5 rounded-xl border border-border bg-secondary/50 cursor-pointer">
                    Add another file
                  </span>
                  <input
                    type="file"
                    className="hidden"
                    accept=".txt,.md,.markdown,.pdf,.docx,.json"
                    onChange={(event) =>
                      run(async () => {
                        const file = event.target.files?.[0];
                        if (!file || !selectedKb) return;
                        await api.uploadDocument(selectedKb.id, file);
                        setSelectedKb(await api.getKnowledgeBase(selectedKb.id));
                        await load();
                      }, "Upload failed.")
                    }
                  />
                </label>
              </div>
            )}
          </Card>

          <Card title="Question">
            <textarea
              className="w-full min-h-28 bg-[#0c1730] border border-border rounded-2xl px-4 py-3 text-base outline-none focus:ring-2 focus:ring-primary/35"
              placeholder="Example: When are refunds issued?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onAsk();
              }}
            />
            <div className="mt-3 flex items-center gap-3">
              <Button disabled={busy} onClick={onAsk}>
                {busy ? "Searching…" : "Ask"}
              </Button>
              <span className="text-xs text-muted-foreground">Press Ctrl+Enter to send</span>
            </div>
          </Card>

          {report && (
            <div className="space-y-5">
              <Card title="Answer">
                <p className="text-[15px] leading-7">{report.query_result?.answer || "No answer was generated."}</p>
              </Card>
              <Card title="Where this came from">
                {!report.query_result?.retrieved.length ? (
                  <p className="text-sm text-muted-foreground">Nothing was retrieved from your files.</p>
                ) : (
                  <ul className="space-y-3">
                    {report.query_result.retrieved.map((item) => (
                      <li key={item.chunk.chunk_id} className="rounded-2xl border border-border p-3">
                        <div className="text-xs text-muted-foreground mb-1">{item.chunk.source}</div>
                        <p className="text-sm leading-6">{item.chunk.content.slice(0, 420)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title="What might be wrong">
                <div className="space-y-3">
                  {report.findings.slice(0, 5).map((finding, idx) => (
                    <div key={idx} className="rounded-2xl border border-border p-3">
                      <div className="flex flex-wrap gap-2 items-center mb-1">
                        <span className="text-sm font-medium">{finding.title}</span>
                        <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{finding.description}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </>
      )}

      {view === "history" && (
        <>
          <h1 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
            History
          </h1>
          <p className="text-muted-foreground">Open a past question to see its answer again.</p>
          <Card>
            {!sessions.length ? (
              <EmptyState
                title="No questions yet"
                body="Ask something in Workspace. It will show up here."
                action={<Button onClick={() => onNavigate("workspace")}>Go to Workspace</Button>}
              />
            ) : (
              <ul className="divide-y divide-border">
                {sessions.map((session) => (
                  <li key={session.id}>
                    <button
                      className="w-full text-left py-3 flex justify-between gap-3"
                      onClick={async () => {
                        const detail = await api.getDebugSession(session.id);
                        setReport(detail.report);
                        setQuery(session.query);
                        onNavigate("workspace");
                      }}
                    >
                      <span className="truncate">{session.query}</span>
                      <Badge tone={session.status === "completed" ? "ok" : "warn"}>{session.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}

      {view === "account" && (
        <>
          <h1 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
            Account
          </h1>
          <p className="text-muted-foreground">Optional. You can use the app as a guest.</p>
          <Card title={authMode === "signin" ? "Sign in" : "Create account"}>
            <p className="text-sm text-muted-foreground mb-4">Currently {String(me?.email || "guest")}</p>
            <div className="flex gap-2 mb-4">
              <Button variant={authMode === "signin" ? "primary" : "ghost"} onClick={() => setAuthMode("signin")}>
                Sign in
              </Button>
              <Button variant={authMode === "register" ? "primary" : "ghost"} onClick={() => setAuthMode("register")}>
                Create account
              </Button>
            </div>
            <div className="space-y-3">
              <Field label="Email">
                <Input type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              </Field>
              <Field label="Password (8+ characters)">
                <Input type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
              </Field>
              <div className="flex gap-2">
                <Button
                  disabled={busy}
                  onClick={() => {
                    const trimmed = email.trim();
                    if (trimmed.length < 3 || !trimmed.includes("@")) {
                      setError("Enter a valid email address.");
                      return;
                    }
                    if (password.length < 8) {
                      setError("Password must be at least 8 characters.");
                      return;
                    }
                    run(async () => {
                      const result =
                        authMode === "register"
                          ? await api.register(trimmed, password)
                          : await api.login(trimmed, password);
                      setAuthToken(result.token);
                      setWorkspaceId(result.workspace_id);
                      setWorkspace(result.workspace_id);
                      await load();
                    }, "Could not sign in.");
                  }}
                >
                  {authMode === "register" ? "Create account" : "Sign in"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setAuthToken(null);
                    load();
                  }}
                >
                  Sign out
                </Button>
              </div>
            </div>
          </Card>
          <button className="text-xs text-muted-foreground underline" onClick={() => onNavigate("code-lab")}>
            Developer tools: Code Lab
          </button>
        </>
      )}
    </div>
  );
}
