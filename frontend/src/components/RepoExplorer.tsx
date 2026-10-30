import React, { useState } from "react";
import {
  Folder,
  Search,
  FileCode,
  CheckCircle2,
  AlertCircle,
  GitBranch,
  GitCommit,
  Download,
  Layers,
  Terminal,
} from "lucide-react";
import { api } from "../services/api";
import { GitRepositoryInfo } from "../types";

export const RepoExplorer: React.FC = () => {
  const [repoPath, setRepoPath] = useState("D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<{
    path: string;
    total_files: number;
    files: string[];
  } | null>(null);
  const [gitInfo, setGitInfo] = useState<GitRepositoryInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Remote Clone State
  const [showClone, setShowClone] = useState(false);
  const [cloneUrl, setCloneUrl] = useState("");
  const [cloneTarget, setCloneTarget] = useState("D:\\AI TASK\\multi-agent-rag-debugger\\data\\cloned_repo");
  const [cloning, setCloning] = useState(false);
  const [cloneSuccess, setCloneSuccess] = useState<string | null>(null);

  const handleScan = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!repoPath.trim()) return;

    try {
      setScanning(true);
      setError(null);
      setCloneSuccess(null);

      // Concurrently scan repository files and fetch Git metadata
      const [filesRes, gitRes] = await Promise.all([
        api.scanRepository(repoPath.trim()),
        api.getGitStatus(repoPath.trim()).catch(() => null),
      ]);

      setScanResult(filesRes);
      setGitInfo(gitRes);
    } catch (err: any) {
      setError(err.message || "Failed to scan repository.");
      setScanResult(null);
      setGitInfo(null);
    } finally {
      setScanning(false);
    }
  };

  const handleClone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cloneUrl.trim() || !cloneTarget.trim()) return;

    try {
      setCloning(true);
      setError(null);
      setCloneSuccess(null);

      const res = await api.cloneRepository({
        remote_url: cloneUrl.trim(),
        target_directory: cloneTarget.trim(),
      });

      setCloneSuccess(`Cloned successfully to ${res.path}`);
      setRepoPath(res.path);
      setShowClone(false);
      // Auto-scan cloned repository
      const [filesRes, gitRes] = await Promise.all([
        api.scanRepository(res.path),
        api.getGitStatus(res.path).catch(() => null),
      ]);
      setScanResult(filesRes);
      setGitInfo(gitRes);
    } catch (err: any) {
      setError(err.message || "Failed to clone repository.");
    } finally {
      setCloning(false);
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm mb-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center space-x-2.5">
          <Folder className="w-5 h-5 text-primary" />
          <div>
            <h3 className="text-base font-bold text-foreground">
              Repository Source Explorer &amp; Git Inspector
            </h3>
            <p className="text-xs text-muted-foreground">
              Audit indexed codebase files, verify Git context, and inspect targets
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowClone(!showClone)}
          className="text-xs px-3 py-1.5 rounded-lg border border-border bg-secondary hover:bg-secondary/80 text-foreground flex items-center space-x-1.5 transition-colors"
        >
          <Download className="w-3.5 h-3.5 text-primary" />
          <span>Clone Remote Repo</span>
        </button>
      </div>

      {showClone && (
        <form onSubmit={handleClone} className="mb-6 p-4 border border-border rounded-lg bg-secondary/20 space-y-3">
          <div className="text-xs font-semibold text-foreground flex items-center space-x-1.5">
            <Download className="w-4 h-4 text-primary" />
            <span>Connect &amp; Clone Remote Git Repository</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-muted-foreground mb-1">Remote URL (HTTPS / Git)</label>
              <input
                type="text"
                required
                value={cloneUrl}
                onChange={(e) => setCloneUrl(e.target.value)}
                placeholder="https://github.com/org/repo.git"
                className="w-full bg-background border border-border rounded px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-muted-foreground mb-1">Local Destination Path</label>
              <input
                type="text"
                required
                value={cloneTarget}
                onChange={(e) => setCloneTarget(e.target.value)}
                placeholder="D:\AI TASK\...\data\cloned_repo"
                className="w-full bg-background border border-border rounded px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
              />
            </div>
          </div>
          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setShowClone(false)}
              className="text-xs px-3 py-1 rounded border border-border text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={cloning}
              className="text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-medium px-4 py-1 rounded transition-colors"
            >
              {cloning ? "Cloning..." : "Clone Repository"}
            </button>
          </div>
        </form>
      )}

      <form onSubmit={handleScan} className="flex gap-2.5 mb-6">
        <input
          type="text"
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="Path to local repository directory..."
          className="flex-1 bg-background border border-border rounded-lg px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
        />
        <button
          type="submit"
          disabled={scanning}
          className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium text-xs px-4 py-2 rounded-lg transition-all shadow-sm flex items-center space-x-1.5 disabled:opacity-50"
        >
          {scanning ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              <span>Scanning...</span>
            </>
          ) : (
            <>
              <Search className="w-3.5 h-3.5" />
              <span>Scan Directory</span>
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="p-3 bg-rose-500/15 border border-rose-500/30 text-rose-300 rounded-lg text-xs flex items-center space-x-2 mb-4">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {cloneSuccess && (
        <div className="p-3 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-lg text-xs flex items-center space-x-2 mb-4">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{cloneSuccess}</span>
        </div>
      )}

      {/* Git Context Header Card */}
      {gitInfo && (
        <div className="border border-border rounded-lg p-4 mb-4 bg-secondary/10 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="space-y-1">
            <span className="text-muted-foreground font-medium flex items-center space-x-1">
              <GitBranch className="w-3.5 h-3.5 text-primary" />
              <span>Branch &amp; Git Status</span>
            </span>
            <div className="font-mono text-foreground font-semibold">
              {gitInfo.is_git ? gitInfo.current_branch : "Not a Git Repository"}
            </div>
            {gitInfo.is_git && (
              <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${gitInfo.is_clean ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
                {gitInfo.is_clean ? "Working Tree Clean" : "Uncommitted Changes Detected"}
              </span>
            )}
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground font-medium flex items-center space-x-1">
              <GitCommit className="w-3.5 h-3.5 text-amber-400" />
              <span>HEAD Commit</span>
            </span>
            <div className="font-mono text-foreground text-[11px] truncate">
              {gitInfo.commit_sha ? gitInfo.commit_sha.slice(0, 10) : "N/A"}
              {gitInfo.commit_author ? ` — ${gitInfo.commit_author}` : ""}
            </div>
            <div className="text-muted-foreground text-[10px] truncate">
              {gitInfo.commit_message || "No commit message"}
            </div>
          </div>

          <div className="space-y-1">
            <span className="text-muted-foreground font-medium flex items-center space-x-1">
              <Layers className="w-3.5 h-3.5 text-blue-400" />
              <span>Detected Tooling</span>
            </span>
            <div className="font-semibold text-foreground">
              {gitInfo.detected_framework || "Generic / Unconfigured"}
            </div>
            <div className="font-mono text-muted-foreground text-[10px] flex items-center space-x-1">
              <Terminal className="w-3 h-3" />
              <span>{gitInfo.default_test_command ? gitInfo.default_test_command.join(" ") : "No test suite detected"}</span>
            </div>
          </div>
        </div>
      )}

      {scanResult && (
        <div className="border border-border rounded-lg overflow-hidden bg-background">
          <div className="px-4 py-2.5 bg-secondary/40 border-b border-border flex items-center justify-between text-xs font-semibold text-foreground flex-wrap gap-2">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="truncate max-w-md">Scanned: {scanResult.path}</span>
            </div>
            <span className="text-muted-foreground font-mono">
              {scanResult.total_files} Valid Source Files Detected
            </span>
          </div>

          <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-96 overflow-y-auto">
            {scanResult.files.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center space-x-2 text-xs font-mono p-2 rounded bg-card border border-border/60 hover:border-primary/40 transition-colors"
              >
                <FileCode className="w-4 h-4 text-primary flex-shrink-0" />
                <span className="truncate text-foreground">{file}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
