"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
  Zap,
  Mail,
  GitBranch,
  MessageSquare,
} from "lucide-react";
import { API, ActionRecord, RiskBadge, formatRelative } from "@/components/shared";

const ACTION_ICONS: Record<string, React.ReactNode> = {
  SEND_EXTERNAL_EMAIL: <Mail size={15} />,
  CREATE_LINEAR_TASK: <GitBranch size={15} />,
  POST_SLACK_MESSAGE: <MessageSquare size={15} />,
  ASSIGN_TASK: <Zap size={15} />,
  RESCHEDULE_MEETING: <AlertTriangle size={15} />,
};

export default function ApprovalsPage() {
  const [actions, setActions] = useState<ActionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetch(`${API}/api/actions/pending-approval`)
      .then((r) => r.json())
      .then((d) => setActions(d.actions ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const approve = async (id: string) => {
    setProcessing(id);
    await fetch(`${API}/api/actions/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_by: "human-operator" }),
    });
    setProcessing(null);
    load();
  };

  const reject = async (id: string) => {
    setProcessing(id);
    await fetch(`${API}/api/actions/${id}/reject`, { method: "POST" });
    setProcessing(null);
    load();
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>Approvals</h1>
      <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 24 }}>
        {actions.length} action{actions.length !== 1 ? "s" : ""} awaiting your approval
      </p>

      {loading && (
        <div style={{ color: "var(--text-muted)", padding: 40, textAlign: "center" }}>
          Loading…
        </div>
      )}

      {!loading && actions.length === 0 && (
        <div className="glass-card" style={{ padding: 48, textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
            No pending approvals
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
            The policy engine will send new approvals here as they come in.
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {actions.map((action) => (
          <div key={action.id} className="glass-card" style={{ padding: 24 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    background: "rgba(139,92,246,0.12)",
                    border: "1px solid rgba(139,92,246,0.3)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--accent-purple)",
                  }}
                >
                  {ACTION_ICONS[action.action_type] ?? <Zap size={15} />}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>
                    {action.action_type.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {formatRelative(action.created_at)}
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <RiskBadge level={action.risk_level} />
              </div>
            </div>

            {/* Evidence / params */}
            <div
              style={{
                background: "rgba(0,0,0,0.2)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "14px 16px",
                marginBottom: 16,
              }}
            >
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Proposed Action Details
              </div>
              {Object.entries(action.params).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 2, textTransform: "capitalize" }}>
                    {k.replace(/_/g, " ")}
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: "var(--text-primary)",
                      whiteSpace: "pre-wrap",
                      fontFamily: k === "body" ? "monospace" : "inherit",
                    }}
                  >
                    {typeof v === "string" ? v : JSON.stringify(v, null, 2)}
                  </div>
                </div>
              ))}
            </div>

            {/* Policy reason */}
            <div
              style={{
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
                marginBottom: 16,
                padding: "10px 12px",
                background: "rgba(139,92,246,0.06)",
                borderRadius: 6,
                border: "1px solid rgba(139,92,246,0.15)",
              }}
            >
              <AlertTriangle size={13} color="var(--accent-purple)" style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                {action.policy_reason}
              </div>
            </div>

            {/* Commitment link */}
            <div style={{ marginBottom: 16 }}>
              <Link
                href={`/commitments/${action.commitment_id}`}
                style={{ fontSize: 12, color: "var(--accent-purple)", textDecoration: "none" }}
              >
                View commitment trace →
              </Link>
            </div>

            {/* Approve / reject */}
            <div style={{ display: "flex", gap: 10 }}>
              <button
                className="btn btn-success"
                disabled={processing === action.id}
                onClick={() => approve(action.id)}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <ThumbsUp size={14} />
                {processing === action.id ? "Processing…" : "Approve & Execute"}
              </button>
              <button
                className="btn btn-danger"
                disabled={processing === action.id}
                onClick={() => reject(action.id)}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <ThumbsDown size={14} />
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
