import React, { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Check,
  X,
  RefreshCw,
  MessageSquare,
  AlertTriangle,
  GitBranch,
  GitCommit,
} from "lucide-react";
import { ApprovalRecord } from "../types";

interface ApprovalBannerProps {
  runId: string;
  currentApprovalStatus: string;
  validationPassed?: boolean | null;
  approvalHistory?: ApprovalRecord[];
  onReview: (status: "approved" | "rejected" | "revision_requested", comment?: string) => Promise<void>;
  onCommit?: (branchName: string, commitMessage: string) => Promise<void>;
}

export const ApprovalBanner: React.FC<ApprovalBannerProps> = ({
  runId,
  currentApprovalStatus,
  validationPassed,
  approvalHistory = [],
  onReview,
  onCommit,
}) => {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showInput, setShowInput] = useState(false);
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [branchName, setBranchName] = useState(`fix/run-${runId.slice(0, 8)}`);
  const [commitMessage, setCommitMessage] = useState(`fix: apply verified fix for run ${runId.slice(0, 8)}`);
  const [commitSuccess, setCommitSuccess] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const handleAction = async (status: "approved" | "rejected" | "revision_requested") => {
    try {
      setSubmitting(true);
      setApiError(null);
      await onReview(status, comment || undefined);
      setComment("");
      setShowInput(false);
    } catch (err: any) {
      setApiError(err.message || "Failed to submit review.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCommitSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onCommit) return;
    try {
      setSubmitting(true);
      setApiError(null);
      await onCommit(branchName, commitMessage);
      setCommitSuccess(`Successfully committed to branch ${branchName}`);
      setShowCommitModal(false);
    } catch (err: any) {
      setApiError(err.message || "Failed to commit patch.");
    } finally {
      setSubmitting(false);
    }
  };

  const isApproved = currentApprovalStatus === "approved";
  const isRejected = currentApprovalStatus === "rejected";
  const isMergeReady = isApproved && validationPassed === true;
  const isValidationFailed = validationPassed === false;
  const hasOverride = approvalHistory.some(ap => ap.comment?.includes("[VALIDATION OVERRIDE]"));

  return (
    <div
      className={`border rounded-xl p-5 mb-6 transition-all ${
        isMergeReady
          ? "bg-emerald-950/20 border-emerald-500/30"
          : isApproved && isValidationFailed
          ? "bg-amber-950/20 border-amber-500/30"
          : isRejected
          ? "bg-rose-950/20 border-rose-500/30"
          : "bg-amber-950/20 border-amber-500/30"
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div
            className={`p-2 rounded-lg border ${
              isMergeReady
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                : isRejected
                ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                : isApproved && isValidationFailed
                ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                : "bg-amber-500/15 border-amber-500/30 text-amber-400"
            }`}
          >
            {isMergeReady ? (
              <ShieldCheck className="w-5 h-5" />
            ) : isRejected ? (
              <ShieldAlert className="w-5 h-5" />
            ) : isApproved && isValidationFailed ? (
              <AlertTriangle className="w-5 h-5" />
            ) : (
              <RefreshCw className="w-5 h-5 animate-spin-slow" />
            )}
          </div>
          <div>
            <div className="font-semibold text-sm text-foreground flex items-center space-x-2 flex-wrap gap-1">
              <span>Human Approval &amp; Deployment Gate</span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase ${
                  isApproved && validationPassed
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                    : isRejected
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                    : "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                }`}
              >
                {currentApprovalStatus}
              </span>
              {isValidationFailed && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase bg-rose-500/20 text-rose-400 border border-rose-500/40">
                  Validation Failed
                </span>
              )}
              {hasOverride && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase bg-orange-500/20 text-orange-400 border border-orange-500/40">
                  Override Active
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {isMergeReady
                ? "Patch verified, validation passed, and approved by reviewer. Ready for branch merge."
                : isApproved && isValidationFailed
                ? hasOverride
                  ? "⚠ Approved with override — validation FAILED. Override reason recorded in audit log. Not eligible for automatic merge."
                  : "⚠ Approved but validation FAILED. Cannot merge until validation passes. Fix the patch or provide an override reason."
                : isRejected
                ? "Patch has been rejected. Revision or additional debugging required."
                : isValidationFailed
                ? "Validation failed. Fix the reported issues before approving. Approval is blocked."
                : "Review the proposed diff above before approving changes. Validation must pass for merge eligibility."}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 self-end sm:self-center flex-wrap gap-2">
          {isMergeReady && onCommit && (
            <button
              disabled={submitting}
              onClick={() => setShowCommitModal(true)}
              className="flex items-center space-x-1.5 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-3 py-1.5 rounded-lg transition-colors shadow-sm"
            >
              <GitCommit className="w-3.5 h-3.5" />
              <span>Commit to Git Branch</span>
            </button>
          )}

          <button
            disabled={submitting || isApproved || isValidationFailed}
            onClick={() => handleAction("approved")}
            title={isValidationFailed ? "Approval blocked: validation failed. Add an override reason in the comment field to override." : ""}
            className="flex items-center space-x-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-3.5 py-1.5 rounded-lg transition-colors shadow-sm"
          >
            <Check className="w-3.5 h-3.5" />
            <span>Approve Patch</span>
          </button>

          <button
            disabled={submitting || isRejected}
            onClick={() => handleAction("rejected")}
            className="flex items-center space-x-1.5 text-xs bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-medium px-3.5 py-1.5 rounded-lg transition-colors shadow-sm"
          >
            <X className="w-3.5 h-3.5" />
            <span>Reject</span>
          </button>

          <button
            onClick={() => setShowInput(!showInput)}
            className="text-xs px-2.5 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground hover:text-foreground transition-colors"
            title="Add review comment or validation override reason"
          >
            <MessageSquare className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {showInput && (
        <div className="mt-4 pt-3 border-t border-border/50 space-y-2">
          {isValidationFailed && (
            <p className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-3 py-1.5">
              ⚠ Validation failed. To override, enter a reason below and click "Approve with Override".
              This exception will be recorded in the audit log.
            </p>
          )}
          <div className="flex gap-2">
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={isValidationFailed ? "Required override reason for approving with failed validation..." : "Add review feedback, instructions, or rejection reason..."}
              className="flex-1 bg-background border border-border rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={() => handleAction("revision_requested")}
              className="text-xs bg-secondary hover:bg-secondary/80 px-3 py-1.5 rounded-lg border border-border font-medium text-foreground transition-colors"
            >
              Request Revision
            </button>
            {isValidationFailed && (
              <button
                disabled={!comment.trim() || submitting}
                onClick={() => handleAction("approved")}
                className="text-xs bg-orange-700 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded-lg border border-orange-500/40 font-medium transition-colors"
              >
                Approve with Override
              </button>
            )}
          </div>
        </div>
      )}

      {showCommitModal && (
        <form onSubmit={handleCommitSubmit} className="mt-4 pt-4 border-t border-border/60 space-y-3 bg-secondary/30 p-4 rounded-lg">
          <div className="flex items-center space-x-2 text-xs font-semibold text-foreground">
            <GitBranch className="w-4 h-4 text-primary" />
            <span>Commit Approved Fix to Git Repository</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-muted-foreground mb-1">Fix Branch Name</label>
              <input
                type="text"
                required
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                className="w-full bg-background border border-border rounded px-2.5 py-1.5 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-muted-foreground mb-1">Commit Message</label>
              <input
                type="text"
                required
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                className="w-full bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={() => setShowCommitModal(false)}
              className="text-xs px-3 py-1 rounded border border-border text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-medium px-4 py-1 rounded transition-colors"
            >
              {submitting ? "Committing..." : "Confirm & Commit"}
            </button>
          </div>
        </form>
      )}

      {commitSuccess && (
        <div className="mt-3 p-2.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded text-xs flex items-center space-x-2">
          <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{commitSuccess}</span>
        </div>
      )}

      {apiError && (
        <div className="mt-3 p-2 bg-rose-500/15 border border-rose-500/30 text-rose-300 rounded text-xs">
          {apiError}
        </div>
      )}

      {approvalHistory.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/40 text-[11px] text-muted-foreground space-y-1">
          <div className="font-semibold text-foreground text-xs">Review Audit Log:</div>
          {approvalHistory.map((ap, idx) => (
            <div key={idx} className="flex items-center space-x-2 flex-wrap">
              <span className="font-mono text-foreground font-medium">{ap.reviewer}</span>
              <span>marked as <strong className="uppercase">{ap.status}</strong></span>
              {ap.comment && <span className="italic">— "{ap.comment}"</span>}
              <span className="text-muted-foreground/60">• {new Date(ap.reviewed_at).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
