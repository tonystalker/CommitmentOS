"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  CheckCircle,
  ThumbsUp,
  Zap,
  ArrowRight,
  TrendingUp,
  Activity,
} from "lucide-react";
import { API, StateBadge, RiskBar, Commitment, formatRelative } from "@/components/shared";

interface DashboardData {
  at_risk: number;
  overdue: number;
  blocked: number;
  completed_today: number;
  approvals_needed: number;
  total: number;
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [recent, setRecent] = useState<Commitment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/dashboard`).then((r) => r.json()),
      fetch(`${API}/api/commitments?limit=5`).then((r) => r.json()),
    ])
      .then(([dash, coms]) => {
        setDashboard(dash);
        setRecent(coms.commitments?.slice(0, 6) ?? []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1
          className="gradient-text"
          style={{ fontSize: 28, fontWeight: 800, marginBottom: 6 }}
        >
          CommitmentOS
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>
          Autonomous commitment recovery · Acme Corp
        </p>
      </div>

      {/* Stat cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 16,
          marginBottom: 32,
        }}
      >
        <StatCard
          icon={<AlertTriangle size={18} color="#f59e0b" />}
          label="At Risk"
          value={dashboard?.at_risk ?? "—"}
          color="#f59e0b"
          href="/commitments?state=AT_RISK"
        />
        <StatCard
          icon={<Clock size={18} color="#ef4444" />}
          label="Overdue"
          value={dashboard?.overdue ?? "—"}
          color="#ef4444"
          href="/commitments?state=OVERDUE"
        />
        <StatCard
          icon={<Activity size={18} color="#ec4899" />}
          label="Blocked"
          value={dashboard?.blocked ?? "—"}
          color="#ec4899"
          href="/commitments?state=BLOCKED"
        />
        <StatCard
          icon={<ThumbsUp size={18} color="#8b5cf6" />}
          label="Approvals Needed"
          value={dashboard?.approvals_needed ?? "—"}
          color="#8b5cf6"
          href="/approvals"
          pulse={!!dashboard?.approvals_needed}
        />
        <StatCard
          icon={<CheckCircle size={18} color="#10b981" />}
          label="Total Tracked"
          value={dashboard?.total ?? "—"}
          color="#10b981"
          href="/commitments"
        />
      </div>

      {/* Recent commitments */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24 }}>
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <h2 style={{ fontSize: 15, fontWeight: 700 }}>Recent Commitments</h2>
            <Link
              href="/commitments"
              style={{
                fontSize: 12,
                color: "var(--accent-purple)",
                display: "flex",
                alignItems: "center",
                gap: 4,
                textDecoration: "none",
              }}
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {loading && (
              <div style={{ color: "var(--text-muted)", fontSize: 13, padding: 20, textAlign: "center" }}>
                Loading…
              </div>
            )}
            {recent.map((c) => (
              <Link
                key={c.id}
                href={`/commitments/${c.id}`}
                style={{ textDecoration: "none" }}
              >
                <div className="glass-card" style={{ padding: "14px 16px" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          marginBottom: 4,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {c.normalized_action}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--text-muted)",
                          display: "flex",
                          gap: 12,
                          alignItems: "center",
                        }}
                      >
                        <span>{formatRelative(c.resolved_deadline)}</span>
                        {c.raw_deadline && (
                          <span style={{ color: "var(--text-secondary)" }}>
                            &ldquo;{c.raw_deadline}&rdquo;
                          </span>
                        )}
                      </div>
                    </div>
                    <div
                      style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}
                    >
                      <StateBadge state={c.state} />
                      <RiskBar score={c.risk_score} />
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Quick run panel */}
        <QuickRunPanel />
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
  href,
  pulse,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: string;
  href: string;
  pulse?: boolean;
}) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <div
        className="glass-card"
        style={{
          padding: "18px 20px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {pulse && (
          <span
            style={{
              position: "absolute",
              top: 10,
              right: 10,
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: color,
              animation: "pulse 2s infinite",
            }}
          />
        )}
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: `${color}18`,
            border: `1px solid ${color}30`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 12,
          }}
        >
          {icon}
        </div>
        <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>
          {value}
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
          {label}
        </div>
      </div>
    </Link>
  );
}

function QuickRunPanel() {
  const [request, setRequest] = useState(
    "Find commitments at risk and take care of whatever you can."
  );
  const [channels, setChannels] = useState("C_PRODUCT_LAUNCH,C_ENGINEERING");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<{ stage: string; detail: string; timestamp: string }[]>([]);

  const run = async () => {
    setRunning(true);
    setEvents([]);

    const res = await fetch(`${API}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_request: request,
        slack_channel_ids: channels.split(",").map((s) => s.trim()).filter(Boolean),
        gmail_query: "is:unread",
        message_limit: 30,
      }),
    });

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      for (const line of text.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6));
            setEvents((prev) => [...prev, event]);
          } catch {}
        }
      }
    }
    setRunning(false);
  };

  const stageColor: Record<string, string> = {
    OBSERVE: "#3b82f6",
    EXTRACT: "#8b5cf6",
    RESOLVE: "#ec4899",
    DEDUP: "#f59e0b",
    RISK: "#ef4444",
    PLAN: "#10b981",
    POLICY: "#6d28d9",
    ACT: "#f59e0b",
    VERIFY: "#10b981",
    DONE: "#10b981",
    ERROR: "#ef4444",
  };

  return (
    <div
      className="glass-card"
      style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <Zap size={16} color="var(--accent-purple)" />
        <h2 style={{ fontSize: 14, fontWeight: 700 }}>Run Agent Loop</h2>
      </div>

      <div>
        <label style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>
          REQUEST
        </label>
        <textarea
          className="input"
          style={{ resize: "none", height: 72, fontSize: 12 }}
          value={request}
          onChange={(e) => setRequest(e.target.value)}
        />
      </div>

      <div>
        <label style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4, display: "block" }}>
          SLACK CHANNELS (comma-separated)
        </label>
        <input
          className="input"
          style={{ fontSize: 12 }}
          value={channels}
          onChange={(e) => setChannels(e.target.value)}
        />
      </div>

      <button
        className="btn btn-primary"
        style={{ width: "100%", justifyContent: "center" }}
        onClick={run}
        disabled={running}
      >
        {running ? (
          <>
            <span
              style={{
                width: 12,
                height: 12,
                border: "2px solid rgba(255,255,255,0.3)",
                borderTop: "2px solid white",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
                display: "inline-block",
              }}
            />
            Running…
          </>
        ) : (
          <>
            <Zap size={14} /> Run Loop
          </>
        )}
      </button>

      {/* Stream events */}
      {events.length > 0 && (
        <div
          style={{
            maxHeight: 260,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {events.map((e, i) => (
            <div
              key={i}
              className="stream-item"
              style={{
                background: `${stageColor[e.stage] ?? "#888"}10`,
                borderLeft: `2px solid ${stageColor[e.stage] ?? "#888"}`,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: stageColor[e.stage] ?? "#888",
                  letterSpacing: "0.5px",
                  minWidth: 52,
                }}
              >
                {e.stage}
              </span>
              <span style={{ color: "var(--text-secondary)", flex: 1 }}>{e.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
