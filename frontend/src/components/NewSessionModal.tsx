import React, { useState } from "react";
import { X, Sparkles, Folder, Play, CheckCircle2 } from "lucide-react";

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    title: string;
    description: string;
    repository_path: string;
    top_k: number;
    use_langgraph: boolean;
    provider: string;
  }) => Promise<void>;
}

export const NewSessionModal: React.FC<NewSessionModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [stackTrace, setStackTrace] = useState("");
  const [repositoryPath, setRepositoryPath] = useState("");
  const [provider, setProvider] = useState("mock"); // Default to reliable mock for instant local demos
  const [useLangGraph, setUseLangGraph] = useState(true);
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleLoadDemo = () => {
    setTitle("Login authentication fails for valid users");
    setDescription(
      "Users report that valid credentials fail authentication due to an unexpected null check exception in login.py. Expected return value should be True."
    );
    // Use sample_project relative/absolute path
    setRepositoryPath("D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim() || !repositoryPath.trim()) {
      setError("Please fill in all required fields.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const combinedDescription = stackTrace.trim()
        ? `${description.trim()}\n\nStack Trace / Error Evidence:\n${stackTrace.trim()}`
        : description.trim();

      await onSubmit({
        title: title.trim(),
        description: combinedDescription,
        repository_path: repositoryPath.trim(),
        top_k: topK,
        use_langgraph: useLangGraph,
        provider,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to execute debugging session.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
          <div className="flex items-center space-x-2.5">
            <Sparkles className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-base font-bold text-foreground">
                Start New Debugging Session
              </h2>
              <p className="text-xs text-muted-foreground">
                Multi-agent RAG investigation, root-cause detection & validation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-rose-500/15 border border-rose-500/30 text-rose-300 rounded-lg text-xs">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleLoadDemo}
              className="text-xs text-primary hover:underline font-medium flex items-center space-x-1"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Load Reproducible Sample Demo</span>
            </button>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Issue Title *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. TypeError: 'NoneType' object is not callable in auth service"
              className="w-full bg-background border border-border rounded-lg px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Issue Description & Symptoms *
            </label>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide observed symptoms, expected vs actual behavior..."
              className="w-full bg-background border border-border rounded-lg px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Stack Trace / Failing Test Output / Error Log (Optional)
            </label>
            <textarea
              rows={3}
              value={stackTrace}
              onChange={(e) => setStackTrace(e.target.value)}
              placeholder="Paste terminal traceback, assertion failure, or error logs to ground retrieval..."
              className="w-full bg-background border border-border rounded-lg px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Target Repository Directory *
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={repositoryPath}
                onChange={(e) => setRepositoryPath(e.target.value)}
                placeholder="D:\AI TASK\multi-agent-rag-debugger\data\sample_project"
                className="w-full bg-background border border-border rounded-lg pl-9 pr-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
              />
              <Folder className="w-4 h-4 text-muted-foreground absolute left-3 top-2.5" />
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">
              Local repository path to index and test. Sandboxed in disposable workspaces.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5">
                LLM Provider
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="mock">Deterministic Mock (Instant / Offline Demo)</option>
                <option value="openrouter">OpenRouter (openai/gpt-oss-20b)</option>
                <option value="openai">OpenAI Direct (gpt-4o-mini)</option>
                <option value="ollama">Ollama Local (llama3)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1.5">
                RAG Evidence Top-K ({topK} Chunks)
              </label>
              <input
                type="range"
                min={1}
                max={15}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-primary mt-2"
              />
            </div>
          </div>

          <div className="pt-2 border-t border-border flex items-center justify-between">
            <label className="flex items-center space-x-2 text-xs text-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useLangGraph}
                onChange={(e) => setUseLangGraph(e.target.checked)}
                className="rounded border-border accent-primary"
              />
              <span>Enable LangGraph Stateful Orchestration</span>
            </label>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 text-xs font-medium rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground disabled:opacity-50 transition-all shadow-sm flex items-center space-x-1.5"
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Analyzing & Debugging...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Run Multi-Agent Pipeline</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
