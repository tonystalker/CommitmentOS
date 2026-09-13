"use client";
import { useState } from "react";
import { Send, MessageSquare, Loader2 } from "lucide-react";
import { API } from "@/components/shared";

interface Message {
  role: "user" | "assistant";
  content: string;
  events?: { stage: string; detail: string }[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm CommitmentOS. Tell me what you need — I can find at-risk commitments, take recovery actions, and answer questions about commitment patterns.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [channels, setChannels] = useState("C_PRODUCT_LAUNCH,C_ENGINEERING");

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    const events: { stage: string; detail: string }[] = [];
    let summary = "";

    try {
      const res = await fetch(`${API}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_request: userMsg,
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
              events.push(event);
              if (event.stage === "DONE") {
                const d = event.data;
                summary = `✅ Loop complete. Found **${d.commitments ?? 0}** commitments — **${d.at_risk ?? 0}** at risk, **${d.blocked ?? 0}** blocked. Verified **${d.actions_verified ?? 0}** action${(d.actions_verified ?? 0) !== 1 ? "s" : ""}. **${d.held_for_approval ?? 0}** held for your approval.`;
              }
            } catch {}
          }
        }
      }
    } catch (e: unknown) {
      summary = `Error: ${e instanceof Error ? e.message : "Unknown error"}`;
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: summary || "Loop completed.",
        events,
      },
    ]);
    setLoading(false);
  };

  const stageColor: Record<string, string> = {
    OBSERVE: "#3b82f6", EXTRACT: "#8b5cf6", RESOLVE: "#ec4899",
    DEDUP: "#f59e0b", RISK: "#ef4444", PLAN: "#10b981",
    POLICY: "#6d28d9", ACT: "#f59e0b", VERIFY: "#10b981",
    DONE: "#10b981", ERROR: "#ef4444",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)" }}>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
          <MessageSquare size={20} color="var(--accent-purple)" /> Control Plane
        </h1>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Slack channels:</span>
          <input
            className="input"
            style={{ fontSize: 12, width: 300 }}
            value={channels}
            onChange={(e) => setChannels(e.target.value)}
          />
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          paddingBottom: 16,
        }}
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: 600,
                padding: "12px 16px",
                borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                background:
                  msg.role === "user"
                    ? "linear-gradient(135deg, #8b5cf6, #6d28d9)"
                    : "var(--bg-card)",
                border: msg.role === "assistant" ? "1px solid var(--border)" : "none",
                fontSize: 14,
                color: "var(--text-primary)",
                lineHeight: 1.6,
              }}
            >
              {/* Render bold text in content */}
              {msg.content.split(/\*\*(.*?)\*\*/g).map((part, j) =>
                j % 2 === 1 ? (
                  <strong key={j} style={{ color: msg.role === "user" ? "white" : "var(--accent-purple)" }}>
                    {part}
                  </strong>
                ) : (
                  part
                )
              )}

              {/* Show events if any */}
              {msg.events && msg.events.length > 0 && (
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 3 }}>
                  {msg.events.map((e, j) => (
                    <div
                      key={j}
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "center",
                        padding: "3px 8px",
                        borderRadius: 4,
                        background: `${stageColor[e.stage] ?? "#888"}12`,
                        borderLeft: `2px solid ${stageColor[e.stage] ?? "#888"}`,
                      }}
                    >
                      <span style={{ fontSize: 9, fontWeight: 700, color: stageColor[e.stage] ?? "#888", minWidth: 48 }}>
                        {e.stage}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{e.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="glass-card" style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 8 }}>
              <Loader2 size={14} color="var(--accent-purple)" style={{ animation: "spin 1s linear infinite" }} />
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Agent running…</span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 10 }}>
        <input
          className="input"
          placeholder="Ask CommitmentOS anything… (e.g. 'Find commitments at risk and take care of whatever you can')"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className="btn btn-primary"
          onClick={send}
          disabled={loading || !input.trim()}
          style={{ flexShrink: 0 }}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
