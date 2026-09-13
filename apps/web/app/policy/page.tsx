"use client";
import { useEffect, useState } from "react";
import { Shield, Lock, Unlock, Edit2, Check, X } from "lucide-react";
import { API } from "@/components/shared";

interface PolicyRule {
  action_type: string;
  risk_level: string;
  default_decision: string;
  description: string;
}

const DECISION_COLORS: Record<string, string> = {
  AUTO: "#10b981",
  APPROVAL: "#f59e0b",
  BLOCK: "#ef4444",
};

const RISK_COLORS: Record<string, string> = {
  LOW: "#10b981",
  MEDIUM: "#f59e0b",
  HIGH: "#ef4444",
  CRITICAL: "#ec4899",
};

export default function PolicyPage() {
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<{ risk_level: string; default_decision: string }>({
    risk_level: "",
    default_decision: "",
  });
  const [saving, setSaving] = useState(false);

  const load = () => {
    fetch(`${API}/api/policy`)
      .then((r) => r.json())
      .then((d) => setRules(d.rules ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const startEdit = (rule: PolicyRule) => {
    setEditing(rule.action_type);
    setEditValues({ risk_level: rule.risk_level, default_decision: rule.default_decision });
  };

  const saveEdit = async (action_type: string) => {
    setSaving(true);
    await fetch(`${API}/api/policy/${action_type}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editValues),
    });
    setSaving(false);
    setEditing(null);
    load();
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, display: "flex", alignItems: "center", gap: 10 }}>
          <Shield size={22} color="var(--accent-purple)" /> Policy Engine
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
          The LLM never modifies these rules — only a human can.
          Every action passes through this table before reaching the executor.
        </p>
      </div>

      {/* Decision legend */}
      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        {["AUTO", "APPROVAL", "BLOCK"].map((d) => (
          <div key={d} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: DECISION_COLORS[d],
              }}
            />
            <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600 }}>{d}</span>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {d === "AUTO" ? "— executed automatically" : d === "APPROVAL" ? "— held for human review" : "— never executed"}
            </span>
          </div>
        ))}
      </div>

      <div className="glass-card" style={{ overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,0.02)" }}>
              {["Action", "Description", "Risk Level", "Default Decision", "Edit"].map((h) => (
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
                <td colSpan={5} style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                  Loading…
                </td>
              </tr>
            )}
            {rules.map((rule, i) => {
              const isEditing = editing === rule.action_type;
              return (
                <tr
                  key={rule.action_type}
                  style={{
                    borderBottom: i < rules.length - 1 ? "1px solid var(--border)" : "none",
                    background: isEditing ? "rgba(139,92,246,0.05)" : "transparent",
                    transition: "background 0.15s",
                  }}
                >
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "monospace" }}>
                      {rule.action_type.replace(/_/g, " ")}
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px", fontSize: 12, color: "var(--text-secondary)", maxWidth: 220 }}>
                    {rule.description}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {isEditing ? (
                      <select
                        value={editValues.risk_level}
                        onChange={(e) => setEditValues((v) => ({ ...v, risk_level: e.target.value }))}
                        style={{
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border)",
                          borderRadius: 6,
                          color: "var(--text-primary)",
                          padding: "4px 8px",
                          fontSize: 12,
                        }}
                      >
                        {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    ) : (
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          color: RISK_COLORS[rule.risk_level] ?? "#888",
                          padding: "2px 10px",
                          background: `${RISK_COLORS[rule.risk_level]}18`,
                          borderRadius: 999,
                          border: `1px solid ${RISK_COLORS[rule.risk_level]}30`,
                        }}
                      >
                        {rule.risk_level}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {isEditing ? (
                      <select
                        value={editValues.default_decision}
                        onChange={(e) => setEditValues((v) => ({ ...v, default_decision: e.target.value }))}
                        style={{
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border)",
                          borderRadius: 6,
                          color: "var(--text-primary)",
                          padding: "4px 8px",
                          fontSize: 12,
                        }}
                      >
                        {["AUTO", "APPROVAL", "BLOCK"].map((d) => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                    ) : (
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {rule.default_decision === "AUTO" ? (
                          <Unlock size={13} color={DECISION_COLORS[rule.default_decision]} />
                        ) : rule.default_decision === "APPROVAL" ? (
                          <Edit2 size={13} color={DECISION_COLORS[rule.default_decision]} />
                        ) : (
                          <Lock size={13} color={DECISION_COLORS[rule.default_decision]} />
                        )}
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            color: DECISION_COLORS[rule.default_decision] ?? "#888",
                          }}
                        >
                          {rule.default_decision}
                        </span>
                      </div>
                    )}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {isEditing ? (
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          className="btn btn-success"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => saveEdit(rule.action_type)}
                          disabled={saving}
                        >
                          <Check size={12} /> Save
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: "4px 10px", fontSize: 12 }}
                          onClick={() => setEditing(null)}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ) : (
                      <button
                        className="btn btn-ghost"
                        style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => startEdit(rule)}
                      >
                        <Edit2 size={12} /> Edit
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div
        style={{
          marginTop: 20,
          padding: "12px 16px",
          background: "rgba(139,92,246,0.06)",
          border: "1px solid rgba(139,92,246,0.15)",
          borderRadius: 8,
          fontSize: 12,
          color: "var(--text-muted)",
        }}
      >
        🔒 Policy changes are applied immediately and logged with the operator identity.
        The LLM never reads or modifies this table directly — it only receives the outcome of policy evaluation.
      </div>
    </div>
  );
}
