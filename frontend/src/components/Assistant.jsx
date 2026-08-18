import React, { useState } from "react";
import { api } from "../services/api"; 

export default function ChatBot({ analysis, onNewResponse }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setInput("");
    
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setLoading(true);

    try {
      const data = await api.askAssistant(userText, analysis);
      
      setMessages((prev) => [...prev, { sender: "bot", text: data.response }]);
      
      if (onNewResponse) {
        onNewResponse(data.response);
      }
    } catch (err) {
      console.error("Chat Error:", err);
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Sorry, an error occurred while connecting to the assistant." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="chat-container glass-panel" 
      style={{ 
        padding: "12px", 
        marginTop: "16px",
        marginLeft: "-5px",          
        marginRight: "auto",        
        width: "150%",              
        maxWidth: "350px",          
        boxSizing: "border-box",    
        borderRadius: "10px",
        display: "flex",
        flexDirection: "column"
      }}
    >
      <div className="chat-header" style={{ marginBottom: "8px" }}>
        <span style={{ fontSize: "15px", fontWeight: "600", color: "#94a3b8", letterSpacing: "1px" }}>
          Elio
        </span>
      </div>

      <div 
        className="messages-list" 
        style={{ 
          height: "180px",          
          overflowY: "auto", 
          display: "flex", 
          flexDirection: "column", 
          gap: "8px",
          marginBottom: "10px",
          paddingRight: "4px"
        }}
      >
        {messages.length === 0 && (
          <p style={{ fontSize: "15px", color: "#64748b", fontStyle: "italic", textAlign: "center", marginTop: "50px" }}>
            Draw an area, run analysis, and ask questions!
          </p>
        )}
        {messages.map((msg, i) => (
          <div 
            key={i} 
            style={{
              alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
              background: msg.sender === "user" ? "rgba(59, 130, 246, 0.15)" : "rgba(255, 255, 255, 0.05)",
              border: msg.sender === "user" ? "1px solid rgba(59, 130, 246, 0.3)" : "1px solid rgba(255, 255, 255, 0.08)",
              padding: "6px 10px",
              borderRadius: "10px",
              maxWidth: "90%",
              fontSize: "11.5px",
              color: "#f8fafc",
              lineHeight: "1.35",
              whiteSpace: "pre-wrap"
            }}
          >
            {msg.text}
          </div>
        ))}
      </div>
      
      <div style={{ display: "flex", gap: "6px" }}>
        <input 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask me..."
          style={{
            flex: 1,
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "10px",
            padding: "6px 10px",
            color: "#ffffff",
            fontSize: "15px",
            outline: "none"
          }}
        />
        <button 
          onClick={handleSend} 
          disabled={loading}
          style={{
            background: "#3b82f6",
            border: "none",
            borderRadius: "10px",
            padding: "6px 12px",
            color: "#ffffff",
            fontSize: "15px",
            fontWeight: "600",
            cursor: "pointer",
            opacity: loading ? 0.6 : 1
          }}
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}