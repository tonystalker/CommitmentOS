import { clsx } from "clsx";

export type CommitmentState =
  | "PROPOSED"
  | "CONFIRMED"
  | "AT_RISK"
  | "BLOCKED"
  | "OVERDUE"
  | "COMPLETED"
  | "CANCELLED";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ActionType =
  | "CREATE_LINEAR_TASK"
  | "UPDATE_LINEAR_STATUS"
  | "POST_SLACK_MESSAGE"
  | "CREATE_REMINDER"
  | "ASSIGN_TASK"
  | "SEND_EXTERNAL_EMAIL"
  | "RESCHEDULE_MEETING"
  | "FINANCIAL_ACTION";

export interface Commitment {
  id: string;
  person_id: string;
  commitment_text: string;
  normalized_action: string;
  raw_deadline: string | null;
  resolved_deadline: string | null;
  state: CommitmentState;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: Record<string, number>;
  related_task_ids: string[];
  created_at: string;
  updated_at: string;
  transition_history: TransitionEvent[];
  action_history: ActionEvent[];
}

export interface TransitionEvent {
  timestamp: string;
  from_state: string;
  to_state: string;
  trigger: string;
  actor: string;
  evidence: Record<string, unknown>;
}

export interface ActionEvent {
  action_type: string;
  timestamp: string;
}

export interface ActionRecord {
  id: string;
  commitment_id: string;
  action_type: ActionType;
  risk_level: RiskLevel;
  status: string;
  params: Record<string, unknown>;
  policy_decision: string;
  policy_reason: string;
  result: Record<string, unknown> | null;
  error: string | null;
  verified: boolean;
  created_at: string;
}

export interface TraceStep {
  id: string;
  stage: string;
  timestamp: string;
  detail: string;
  data: Record<string, unknown>;
}

const STATE_CONFIG: Record<CommitmentState, { label: string; class: string }> = {
  PROPOSED:  { label: "Proposed",  class: "badge-proposed" },
  CONFIRMED: { label: "Confirmed", class: "badge-confirmed" },
  AT_RISK:   { label: "At Risk",   class: "badge-at-risk" },
  BLOCKED:   { label: "Blocked",   class: "badge-blocked" },
  OVERDUE:   { label: "Overdue",   class: "badge-overdue" },
  COMPLETED: { label: "Completed", class: "badge-completed" },
  CANCELLED: { label: "Cancelled", class: "badge-cancelled" },
};

const RISK_CONFIG: Record<RiskLevel, { label: string; class: string; color: string }> = {
  LOW:      { label: "Low",      class: "badge-low",      color: "#10b981" },
  MEDIUM:   { label: "Medium",   class: "badge-medium",   color: "#f59e0b" },
  HIGH:     { label: "High",     class: "badge-high",     color: "#ef4444" },
  CRITICAL: { label: "Critical", class: "badge-critical", color: "#ec4899" },
};

export function StateBadge({ state }: { state: CommitmentState }) {
  const cfg = STATE_CONFIG[state] ?? { label: state, class: "badge-proposed" };
  return <span className={clsx("badge", cfg.class)}>{cfg.label}</span>;
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const cfg = RISK_CONFIG[level] ?? { label: level, class: "badge-low", color: "#10b981" };
  return <span className={clsx("badge", cfg.class)}>{cfg.label}</span>;
}

export function RiskBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.75 ? "#ec4899" : score >= 0.55 ? "#ef4444" : score >= 0.35 ? "#f59e0b" : "#10b981";
  return (
    <div className="risk-bar-track" style={{ width: 80 }}>
      <div className="risk-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export function formatRelative(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const diff = (d.getTime() - Date.now()) / 1000;
  if (Math.abs(diff) < 60) return "just now";
  if (Math.abs(diff) < 3600) return `${Math.round(Math.abs(diff) / 60)}m ${diff < 0 ? "ago" : "from now"}`;
  if (Math.abs(diff) < 86400) return `${Math.round(Math.abs(diff) / 3600)}h ${diff < 0 ? "ago" : "from now"}`;
  return `${Math.round(Math.abs(diff) / 86400)}d ${diff < 0 ? "ago" : "from now"}`;
}

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
