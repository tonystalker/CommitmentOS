"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitCommitHorizontal,
  CheckSquare,
  Shield,
  MessageSquare,
  FlaskConical,
  Zap,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/commitments", label: "Commitments", icon: GitCommitHorizontal },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/policy", label: "Policy Engine", icon: Shield },
  { href: "/chat", label: "Control Plane", icon: MessageSquare },
  { href: "/eval", label: "Eval Dashboard", icon: FlaskConical },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        width: 220,
        minHeight: "100vh",
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "20px 12px",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ padding: "0 4px 24px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "linear-gradient(135deg, #8b5cf6, #3b82f6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Zap size={16} color="white" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
              CommitmentOS
            </div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.5px" }}>
              COMMITMENT ENGINE
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, marginTop: 16, display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              <Icon size={15} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: "12px 4px 0",
          borderTop: "1px solid var(--border)",
          fontSize: 11,
          color: "var(--text-muted)",
        }}
      >
        <div style={{ marginBottom: 2 }}>Acme Corp · Demo</div>
        <div>CommitmentOS v0.1</div>
      </div>
    </aside>
  );
}
