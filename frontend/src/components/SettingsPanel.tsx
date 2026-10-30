import React, { useState, useEffect } from "react";
import { Sliders, Save, CheckCircle2, AlertCircle, Shield } from "lucide-react";
import { SystemSettings } from "../types";
import { api } from "../services/api";

export const SettingsPanel: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form states
  const [provider, setProvider] = useState("mock");
  const [llmModel, setLlmModel] = useState("");
  const [openaiModel, setOpenaiModel] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(800);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await api.getSettings();
      setSettings(data);
      setProvider(data.llm_provider);
      setLlmModel(data.llm_model);
      setOpenaiModel(data.openai_model);
      setOllamaModel(data.ollama_model);
      setTemperature(data.llm_temperature);
      setMaxTokens(data.llm_max_tokens);
    } catch (err: any) {
      setMessage({ type: "error", text: "Failed to load system settings." });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setMessage(null);
      const updated = await api.updateSettings({
        llm_provider: provider,
        llm_model: llmModel,
        openai_model: openaiModel,
        ollama_model: ollamaModel,
        llm_temperature: temperature,
        llm_max_tokens: maxTokens,
      });
      setSettings(updated);
      setMessage({ type: "success", text: "Runtime settings updated successfully!" });
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to save settings." });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground text-xs">Loading settings...</div>;
  }

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm mb-6 max-w-3xl">
      <div className="flex items-center space-x-2.5 mb-5">
        <Sliders className="w-5 h-5 text-primary" />
        <div>
          <h3 className="text-base font-bold text-foreground">
            System Configuration & LLM Providers
          </h3>
          <p className="text-xs text-muted-foreground">
            Manage provider connections, model parameters, and sandbox execution guardrails
          </p>
        </div>
      </div>

      {message && (
        <div
          className={`p-3 rounded-lg text-xs flex items-center space-x-2 mb-4 ${
            message.type === "success"
              ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/15 border border-rose-500/30 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Active LLM Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="mock">Deterministic Mock (Offline / No Key Required)</option>
              <option value="openrouter">OpenRouter API</option>
              <option value="openai">OpenAI API (Direct)</option>
              <option value="ollama">Ollama Local Instance</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              OpenRouter Model Identifier
            </label>
            <input
              type="text"
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              OpenAI Direct Model
            </label>
            <input
              type="text"
              value={openaiModel}
              onChange={(e) => setOpenaiModel(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Ollama Local Model Tag
            </label>
            <input
              type="text"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-border">
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Temperature ({temperature})
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Max Generation Tokens
            </label>
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value))}
              className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        <div className="p-4 bg-secondary/30 rounded-lg border border-border flex items-start space-x-3 text-xs text-muted-foreground">
          <Shield className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-foreground">Sandbox Security & Persistence Guardrails</div>
            <p className="mt-0.5 text-[11px]">
              Sandbox timeout: {settings?.sandbox_timeout_seconds}s • Database: {settings?.database_url}
            </p>
          </div>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium text-xs px-5 py-2 rounded-lg transition-all shadow-sm flex items-center space-x-1.5 disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? "Saving Changes..." : "Save Runtime Settings"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
