interface SourcesCitationProps {
  sources: string[];
}

export default function SourcesCitation({ sources }: SourcesCitationProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
      <span style={{ fontSize: 10, color: "#555" }}>Sources:</span>
      {sources.map((source, i) => (
        <span
          key={i}
          style={{
            fontSize: 10,
            padding: "1px 7px",
            borderRadius: 10,
            background: "#1a1a2a",
            color: "#888",
            border: "1px solid #252535",
          }}
        >
          {source}
        </span>
      ))}
    </div>
  );
}
