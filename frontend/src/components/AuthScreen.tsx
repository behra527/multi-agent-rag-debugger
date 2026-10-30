import React, { useState } from "react";
import { Sparkles } from "lucide-react";
import { api, setAuthToken, setWorkspaceId } from "../services/api";
import { Button, Field, Input } from "./ui";

export function AuthScreen({
  onAuthed,
}: {
  onAuthed: (profile: { email: string; workspace_id: string }) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (trimmed.length < 3 || !trimmed.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = mode === "register" ? await api.register(trimmed, password) : await api.login(trimmed, password);
      setAuthToken(result.token);
      setWorkspaceId(result.workspace_id);
      onAuthed({ email: result.email, workspace_id: result.workspace_id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-3xl border border-border bg-card p-8 shadow-[var(--card-shadow)]">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="text-lg font-semibold tracking-tight">Atlas</div>
            <div className="text-xs text-muted-foreground">Your inbox is private to this account.</div>
          </div>
        </div>
        <div className="flex gap-2 mb-5">
          <Button type="button" variant={mode === "login" ? "primary" : "ghost"} onClick={() => setMode("login")}>
            Sign in
          </Button>
          <Button type="button" variant={mode === "register" ? "primary" : "ghost"} onClick={() => setMode("register")}>
            Register
          </Button>
        </div>
        {error && <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm">{error}</div>}
        <div className="space-y-3">
          <Field label="Email">
            <Input type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password (8+ characters)">
            <Input type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy ? "Working…" : mode === "register" ? "Create account" : "Sign in"}
          </Button>
        </div>
      </form>
    </div>
  );
}
