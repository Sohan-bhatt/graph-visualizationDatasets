interface ThoughtProcessProps {
  thought: string;
  isStreaming: boolean;
}

export default function ThoughtProcess({ thought, isStreaming }: ThoughtProcessProps) {
  if (!thought && !isStreaming) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        fontSize: 11,
        color: "#666",
        fontStyle: "italic",
        background: "#14141f",
        borderRadius: 8,
        padding: "8px 12px",
        marginBottom: 4,
        border: "1px solid #1e1e2e",
      }}
    >
      <div style={{ marginTop: 2 }}>
        {isStreaming ? (
          <div style={{ display: "flex", gap: 3 }}>
            <span style={{ width: 5, height: 5, background: "#3B82F6", borderRadius: "50%", animation: "bounce 1s infinite 0ms" }} />
            <span style={{ width: 5, height: 5, background: "#3B82F6", borderRadius: "50%", animation: "bounce 1s infinite 150ms" }} />
            <span style={{ width: 5, height: 5, background: "#3B82F6", borderRadius: "50%", animation: "bounce 1s infinite 300ms" }} />
          </div>
        ) : (
          <span style={{ color: "#10B981" }}>&#10003;</span>
        )}
      </div>
      <span style={{ lineHeight: 1.5 }}>{thought || "Thinking..."}</span>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-4px); }
        }
      `}</style>
    </div>
  );
}
