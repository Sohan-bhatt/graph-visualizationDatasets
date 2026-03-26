import { useState, useRef, useEffect, useMemo } from "react";
import { Send, Trash2 } from "lucide-react";
import { useChatStore } from "../hooks/useChat";
import { useGraphStore } from "../hooks/useGraph";
import ThoughtProcess from "./ThoughtProcess";
import SourcesCitation from "./SourcesCitation";

interface ChatPanelProps {
  onHighlight: (ids: string[], focalNodeId?: string) => void;
}

export default function ChatPanel({ onHighlight }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, isStreaming, currentThought, sendMessage, clearMessages } = useChatStore();
  const graphNodes = useGraphStore((state) => state.nodes);

  const graphNodeLookup = useMemo(() => {
    const lookup = new Map<string, string>();
    for (const node of graphNodes) {
      lookup.set(node.id, node.label);
    }
    return lookup;
  }, [graphNodes]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentThought]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    await sendMessage(text, onHighlight);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = [
    "Which products have the most billing documents?",
    "Trace billing doc 90504248",
    "Show incomplete flows - delivered but not billed",
    "List all sales orders",
  ];

  const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const renderMessageWithHighlights = (content: string, highlightedIds?: string[]) => {
    const terms = new Set<string>();

    for (const id of highlightedIds || []) {
      if (id) terms.add(id);
      const label = graphNodeLookup.get(id);
      if (label && label.trim().length > 2) {
        terms.add(label.trim());
      }
    }

    if (terms.size === 0) {
      return <div style={{ whiteSpace: "pre-wrap" }}>{content}</div>;
    }

    const sortedTerms = Array.from(terms)
      .sort((a, b) => b.length - a.length)
      .map((term) => escapeRegex(term));

    const pattern = new RegExp(`(${sortedTerms.join("|")})`, "gi");
    const parts = content.split(pattern);

    return (
      <div style={{ whiteSpace: "pre-wrap" }}>
        {parts.map((part, index) => {
          const isMatch = Array.from(terms).some((term) => term.toLowerCase() === part.toLowerCase());
          if (!isMatch) return <span key={index}>{part}</span>;

          return (
            <mark
              key={index}
              style={{
                background: "rgba(250, 204, 21, 0.2)",
                color: "#fde68a",
                padding: "0 4px",
                borderRadius: 6,
                border: "1px solid rgba(250, 204, 21, 0.28)",
              }}
            >
              {part}
            </mark>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#0f0f1a" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid #1e1e2e" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5" }}>Query Assistant</div>
          <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>Ask about orders, deliveries, billing, payments</div>
        </div>
        <button
          onClick={clearMessages}
          style={{ padding: 6, background: "transparent", border: "none", cursor: "pointer", color: "#555" }}
          title="Clear chat"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "32px 0" }}>
            <p style={{ color: "#555", fontSize: 12, marginBottom: 12 }}>Try asking:</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    fontSize: 11,
                    padding: "8px 12px",
                    background: "#14141f",
                    color: "#aaa",
                    borderRadius: 8,
                    border: "1px solid #1e1e2e",
                    cursor: "pointer",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#1a1a2a")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "#14141f")}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div
              style={{
                maxWidth: "88%",
                borderRadius: 16,
                padding: "10px 14px",
                fontSize: 12,
                lineHeight: 1.6,
                ...(msg.role === "user"
                  ? { background: "#1d4ed8", color: "#fff" }
                  : msg.is_guardrailed
                  ? { background: "rgba(120,53,15,0.15)", border: "1px solid #78350f", color: "#fcd34d" }
                  : { background: "#14141f", color: "#ddd", border: "1px solid #1e1e2e" }),
              }}
            >
              {msg.role === "assistant" && msg.thought && (
                <div style={{ fontSize: 10, color: "#666", fontStyle: "italic", marginBottom: 6, paddingBottom: 6, borderBottom: "1px solid #1e1e2e" }}>
                  {msg.thought}
                </div>
              )}
              {renderMessageWithHighlights(msg.content, msg.highlighted_ids)}
              {msg.role === "assistant" && msg.sources && <SourcesCitation sources={msg.sources} />}
              {msg.role === "assistant" && msg.sql && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{ fontSize: 10, color: "#555", cursor: "pointer" }}>View SQL</summary>
                  <pre
                    style={{
                      fontSize: 10,
                      color: "#888",
                      background: "#0a0a14",
                      borderRadius: 6,
                      padding: 8,
                      marginTop: 4,
                      overflowX: "auto",
                      fontFamily: '"Fira Code", monospace',
                    }}
                  >
                    {msg.sql}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}

        {isStreaming && currentThought && <ThoughtProcess thought={currentThought} isStreaming={true} />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid #1e1e2e" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the O2C data..."
            disabled={isStreaming}
            style={{
              flex: 1,
              background: "#14141f",
              color: "#e5e5e5",
              fontSize: 12,
              borderRadius: 10,
              padding: "10px 14px",
              border: "1px solid #1e1e2e",
              outline: "none",
              opacity: isStreaming ? 0.5 : 1,
            }}
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            style={{
              padding: "10px 14px",
              background: isStreaming || !input.trim() ? "#1e1e2e" : "#1d4ed8",
              border: "none",
              borderRadius: 10,
              color: isStreaming || !input.trim() ? "#444" : "#fff",
              cursor: isStreaming || !input.trim() ? "default" : "pointer",
              transition: "background 0.15s",
              display: "flex",
              alignItems: "center",
            }}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
