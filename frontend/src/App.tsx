import { useEffect, useRef, useState } from "react";
import "./index.css";

const WS_BASE = "wss://chat-backend-fxwq.onrender.com";

type Msg = {
  id?: number;
  text: string;
  sender: string;
  status?: string;
};

export default function App() {
  const [username, setUsername] = useState("");
  const [receiver, setReceiver] = useState("");
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [messageText, setMessageText] = useState("");
  const [typingText, setTypingText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeout = useRef<number | null>(null);
  const isTypingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // CONNECT
  const connect = () => {
    if (!username) return;

    const ws = new WebSocket(`${WS_BASE}/ws/${username}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      setTypingText("");
      isTypingRef.current = false;
    };

    ws.onmessage = (event) => {
      const data = event.data;

      // READ RECEIPT
      if (data.startsWith("READ|")) {
        const id = Number(data.split("|")[1]);
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, status: "✔✔" } : m))
        );
        return;
      }

      // TYPING
      if (data.startsWith("TYPING|")) {
        setTypingText(`${data.split("|")[1]} is typing...`);
        return;
      }

      if (data.startsWith("STOP|")) {
        setTypingText("");
        return;
      }

      // MESSAGE
      if (data.startsWith("MSG|")) {
        const [, id, sender, , text, status] = data.split("|");

        setMessages((prev) => {
          if (prev.some((m) => m.id === Number(id))) return prev;
          return [...prev, { id: Number(id), sender, text, status }];
        });
      }
    };
  };

  // SEND MESSAGE
  const sendMessage = () => {
    if (!wsRef.current || !receiver || !messageText) return;

    wsRef.current.send(`MSG|${receiver}|${messageText}`);
    wsRef.current.send(`STOP|${receiver}`);
    isTypingRef.current = false;
    setMessageText("");
  };

  // TYPING HANDLER (PRODUCTION SAFE)
  const handleTyping = () => {
    if (!wsRef.current || !receiver) return;

    // Send TYPE only once
    if (!isTypingRef.current) {
      wsRef.current.send(`TYPE|${receiver}`);
      isTypingRef.current = true;
    }

    // Reset STOP timer
    if (typingTimeout.current) {
      window.clearTimeout(typingTimeout.current);
    }

    typingTimeout.current = window.setTimeout(() => {
      wsRef.current?.send(`STOP|${receiver}`);
      isTypingRef.current = false;
    }, 1500); // ⬅ IMPORTANT for Render latency
  };

  return (
    <div className="app-root">
      <div className="chat-box">
        <h2>Private Chat</h2>

        <input
          placeholder="Your username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={connected}
        />

        <button onClick={connect} disabled={connected}>
          {connected ? "Connected" : "Join"}
        </button>

        <input
          placeholder="Chat with (username)"
          value={receiver}
          onChange={(e) => setReceiver(e.target.value)}
        />

        <div className="messages">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`msg ${m.sender === username ? "me" : "other"}`}
            >
              <div className="bubble">
                {m.text}
                {m.sender === username && (
                  <span className="tick">{m.status || "✔"}</span>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="typing">{typingText}</div>

        <input
          placeholder="Type message..."
          value={messageText}
          onChange={(e) => {
            setMessageText(e.target.value);
            handleTyping();
          }}
          disabled={!connected}
        />

        <button onClick={sendMessage} disabled={!connected}>
          Send
        </button>
      </div>
    </div>
  );
}
