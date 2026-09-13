"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Search, ChevronRight } from "lucide-react";
import {
  API,
  Commitment,
  CommitmentState,
  StateBadge,
  RiskBadge,
  RiskBar,
  formatRelative,
} from "@/components/shared";

const STATES: CommitmentState[] = [
  "AT_RISK",
  "OVERDUE",
  "BLOCKED",
  "CONFIRMED",
  "PROPOSED",
  "COMPLETED",
  "CANCELLED",
];

function CommitmentsContent() {
  const params = useSearchParams();
  const initialState = params.get("state") as CommitmentState | null;

  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [filter, setFilter] = useState<CommitmentState | "ALL">(initialState ?? "ALL");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const url =
      filter === "ALL"
        ? `${API}/api/commitments`
        : `${API}/api/commitments?state=${filter}`;
    setLoading(true);
    fetch(url)
      .then((r) => r.json())
      .then((d) => setCommitments(d.commitments ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  const filtered = commitments.filter(
    (c) =>
      !search ||
      c.normalized_action.toLowerCase().includes(search.toLowerCase()) ||
      c.commitment_text.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6 }}>
        Commitments
      </h1>
      <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 24 }}>
        {filtered.length} commitment{filtered.length !== 1 ? "s" : ""}
        {filter !== "ALL" ? ` · ${filter.replace("_", " ")}` : ""}
      </p>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        {/* Search */}
        <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
          <Search
            size={14}
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-muted)",
            }}
          />
          <input
            className="input"
            style={{ paddingLeft: 32 }}
            placeholder="Search commitments…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* State filters */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button
            className={`btn ${filter === "ALL" ? "btn-primary" : "btn-ghost"}`}
            style={{ padding: "6px 14px", fontSize: 12 }}
            onClick={() => setFilter("ALL")}
          >
            All
          </button>
          {STATES.map((s) => (
            <button
              key={s}
              className={`btn ${filter === s ? "btn-primary" : "btn-ghost"}`}
              style={{ padding: "6px 14px", fontSize: 12 }}
              onClick={() => setFilter(s)}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="glass-card" style={{ overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr
              style={{
                borderBottom: "1px solid var(--border)",
                background: "rgba(255,255,255,0.02)",
              }}
            >
              {["Action", "State", "Risk", "Deadline", "Confidence", ""].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "10px 16px",
                    textAlign: "left",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    letterSpacing: "0.5px",
                    textTransform: "uppercase",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                  Loading…
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                  No commitments found.
                </td>
              </tr>
            )}
            {filtered.map((c, i) => (
              <tr
                key={c.id}
                style={{
                  borderBottom: i < filtered.length - 1 ? "1px solid var(--border)" : "none",
                  cursor: "pointer",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) =>
                  ((e.currentTarget as HTMLElement).style.background = "rgba(139,92,246,0.04)")
                }
                onMouseLeave={(e) =>
                  ((e.currentTarget as HTMLElement).style.background = "transparent")
                }
              >
                <td style={{ padding: "12px 16px" }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: "var(--text-primary)",
                      maxWidth: 320,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.normalized_action}
                  </div>
                  {c.related_task_ids.length === 0 && (
                    <div style={{ fontSize: 11, color: "#ef444460", marginTop: 2 }}>
                      No Linear task
                    </div>
                  )}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <StateBadge state={c.state} />
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <RiskBadge level={c.risk_level} />
                    <RiskBar score={c.risk_score} />
                  </div>
                </td>
                <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--text-secondary)" }}>
                  <div>{formatRelative(c.resolved_deadline)}</div>
                  {c.raw_deadline && (
                    <div style={{ color: "var(--text-muted)", fontSize: 11 }}>
                      &ldquo;{c.raw_deadline}&rdquo;
                    </div>
                  )}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {Object.entries(c.confidence).map(([k, v]) => (
                      <div
                        key={k}
                        style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 10 }}
                      >
                        <span style={{ color: "var(--text-muted)", minWidth: 60 }}>
                          {k.replace("_", " ")}
                        </span>
                        <div className="risk-bar-track" style={{ width: 40 }}>
                          <div
                            className="risk-bar-fill"
                            style={{
                              width: `${Math.round(v * 100)}%`,
                              background:
                                v >= 0.9 ? "#10b981" : v >= 0.7 ? "#f59e0b" : "#ef4444",
                            }}
                          />
                        </div>
                        <span style={{ color: "var(--text-secondary)" }}>
                          {Math.round(v * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <Link href={`/commitments/${c.id}`}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}>
                      <ChevronRight size={14} /> Trace
                    </button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CommitmentsPage() {
  return (
    <Suspense
      fallback={
        <div style={{ color: "var(--text-muted)", padding: 40, textAlign: "center" }}>
          Loading commitments...
        </div>
      }
    >
      <CommitmentsContent />
    </Suspense>
  );
}

