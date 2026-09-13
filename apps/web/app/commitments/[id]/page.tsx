"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Eye,
  Cpu,
  UserCheck,
  GitMerge,
  TrendingUp,
  Shield,
  Zap,
  CheckCircle,
  Clock,
  AlertTriangle,
} from "lucide-react";
import {
  API,
  Commitment,
  TraceStep,
  StateBadge,
  RiskBadge,
  RiskBar,
  formatRelative,
} from "@/components/shared";

const STAGE_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  OBSERVE:    { icon: <Eye size={14} />,          color: "#3b82f6",  label: "Observe" },
  EXTRACT:    { icon: <Cpu size={14} />,           color: "#8b5cf6",  label: "Extract" },
  RESOLVE:    { icon: <UserCheck size={14} />,     color: "#ec4899",  label: "Resolve" },
  DEDUP:      { icon: <GitMerge size={14} />,      color: "#f59e0b",  label: "Dedup" },
  RISK:       { icon: <TrendingUp size={14} />,    color: "#ef4444",  label: "Risk" },
  PLAN:       { icon: <AlertTriangle size={14} />, color: "#10b981",  label: "Plan" },
  POLICY:     { icon: <Shield size={14} />,        color: "#6d28d9",  label: "Policy" },
  ACT:        { icon: <Zap size={14} />,           color: "#f59e0b",  label: "Act" },
  VERIFY:     { icon: <CheckCircle size={14} />,   color: "#10b981",  label: "Verify" },
};

export default function CommitmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [commitment, setCommitment] = useState<Commitment | null>(null);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      fetch(`${API}/api/commitments/${id}`).then((r) => r.json()),
      fetch(`${API}/api/commitments/${id}/trace`).then((r) => r.json()),
    ])
      .then(([c, t]) => {
        setCommitment(c);
        setTrace(t.trace ?? []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ color: "var(--text-muted)", padding: 40, textAlign: "center" }}>
        Loading…
      </div>
    );
  }

  if (!commitment) {
    return (
      <div style={{ color: "var(--text-muted)", padding: 40, textAlign: "center" }}>
        Commitment not found.
      </div>
    );
  }

  return (
    <div>
      {/* Back */}
      <button
        className="btn btn-ghost"
        style={{ marginBottom: 20, padding: "6px 12px" }}
        onClick={() => router.back()}
      >
        ← Back
      </button>

      {/* Header */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 16, justifyContent: "space-between", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: "var(--text-primary)" }}>
              {commitment.normalized_action}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "monospace", marginBottom: 16 }}>
              ID: {commitment.id}
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <StateBadge state={commitment.state} />
              <RiskBadge level={commitment.risk_level} />
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                Risk score: {Math.round(commitment.risk_score * 100)}%
              </span>
              <RiskBar score={commitment.risk_score} />
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <InfoRow label="Deadline" value={commitment.raw_deadline ?? "—"} />
            <InfoRow label="Resolved" value={formatRelative(commitment.resolved_deadline)} />
            <InfoRow label="Linear tasks" value={commitment.related_task_ids.join(", ") || "None"} />
            <InfoRow label="Created" value={formatRelative(commitment.created_at)} />
          </div>
        </div>

        {/* Confidence */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", marginBottom: 10, letterSpacing: "0.5px", textTransform: "uppercase" }}>
            Confidence Dimensions
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {Object.entries(commitment.confidence).map(([k, v]) => (
              <div key={k} style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 80 }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "capitalize" }}>
                  {k.replace(/_/g, " ")}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div className="risk-bar-track" style={{ width: 60 }}>
                    <div
                      className="risk-bar-fill"
                      style={{
                        width: `${Math.round(v * 100)}%`,
                        background: v >= 0.9 ? "#10b981" : v >= 0.7 ? "#f59e0b" : "#ef4444",
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)" }}>
                    {Math.round(v * 100)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 24 }}>
        {/* Trace Viewer */}
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <Eye size={16} color="var(--accent-purple)" /> Trace Viewer
            <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 400 }}>
              OBSERVE → EXTRACT → RESOLVE → DEDUP → RISK → PLAN → POLICY → ACT → VERIFY
            </span>
          </h2>

          {trace.length === 0 && (
            <div className="glass-card" style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              No trace steps yet. Run the agent loop to generate trace data.
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {trace.map((step, i) => {
              const cfg = STAGE_CONFIG[step.stage] ?? { icon: <Clock size={14} />, color: "#9494b8", label: step.stage };
              const isLast = i === trace.length - 1;

              return (
                <div key={step.id} style={{ display: "flex", gap: 14, position: "relative" }}>
                  {/* Connector */}
                  {!isLast && (
                    <div
                      style={{
                        position: "absolute",
                        left: 19,
                        top: 40,
                        bottom: 0,
                        width: 2,
                        background: `linear-gradient(to bottom, ${cfg.color}60, transparent)`,
                        zIndex: 0,
                      }}
                    />
                  )}

                  {/* Icon */}
                  <div
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: "50%",
                      background: `${cfg.color}18`,
                      border: `2px solid ${cfg.color}40`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      zIndex: 1,
                      color: cfg.color,
                    }}
                  >
                    {cfg.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, paddingBottom: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: cfg.color, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                        {cfg.label}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {new Date(step.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="glass-card" style={{ padding: "10px 14px" }}>
                      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6 }}>
                        {step.detail}
                      </div>
                      {Object.keys(step.data).length > 0 && (
                        <pre
                          style={{
                            fontSize: 11,
                            color: "var(--text-muted)",
                            background: "rgba(0,0,0,0.2)",
                            padding: "6px 8px",
                            borderRadius: 6,
                            overflow: "auto",
                            fontFamily: "monospace",
                          }}
                        >
                          {JSON.stringify(step.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Transition history */}
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>State History</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(commitment.transition_history ?? []).map((t, i) => (
              <div key={i} className="glass-card" style={{ padding: "12px 14px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{t.from_state}</span>
                  <ArrowLeft size={10} color="var(--text-muted)" style={{ transform: "rotate(180deg)" }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--accent-purple)" }}>{t.to_state}</span>
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  trigger: {t.trigger}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>
                  {new Date(t.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
            {(!commitment.transition_history || commitment.transition_history.length === 0) && (
              <div style={{ color: "var(--text-muted)", fontSize: 12 }}>No transitions yet.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <span style={{ color: "var(--text-muted)", minWidth: 80 }}>{label}:</span>
      <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function ArrowLeft({ size, color, style }: { size: number; color: string; style?: React.CSSProperties }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
      <path d="M19 12H5M12 5l-7 7 7 7" />
    </svg>
  );
}
