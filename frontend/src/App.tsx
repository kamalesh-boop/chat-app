import { useEffect, useRef, useState } from "react";
import "./index.css";

const WS_BASE = "wss://chat-backend-fxwq.onrender.com";

type Msg = {
  id: number;
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
  const [receiverOnline, setReceiverOnline] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeout = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  /* ================= AUTO SCROLL ================= */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingText]);

  /* ================= CLEANUP ================= */
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  /* ================= CONNECT ================= */
  const connect = () => {
    if (!username || connected) return;

    const ws = new WebSocket(`${WS_BASE}/ws/${username}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      setTypingText("");
      setReceiverOnline(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onmessage = (event) => {
      const data: string = event.data;

      /* ===== STATUS ===== */
      if (data.startsWith("STATUS|")) {
        const [, user, state] = data.split("|");
        if (user === receiver) {
          setReceiverOnline(state === "online");
        }
        return;
      }

      /* ===== READ RECEIPT ===== */
      if (data.startsWith("READ|")) {
        const id = Number(data.split("|")[1]);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id ? { ...m, status: "✔✔" } : m
          )
        );
        return;
      }

      /* ===== TYPING ===== */
      if (data.startsWith("TYPING|")) {
        const typingUser = data.split("|")[1];
        if (typingUser === receiver) {
          setTypingText(`${typingUser} is typing...`);
        }
        return;
      }

      if (data.startsWith("STOP|")) {
        setTypingText("");
        return;
      }

      /* ===== MESSAGE ===== */
      if (data.startsWith("MSG|")) {
        const [, id, sender, , text, status] = data.split("|");
        const msgId = Number(id);

        setMessages((prev) => {
          if (prev.some((m) => m.id === msgId)) return prev;
          return [...prev, { id: msgId, sender, text, status }];
        });
      }
    };
  };

  /* ================= SEND MESSAGE ================= */
  const sendMessage = () => {
    if (!wsRef.current || !receiver || !messageText.trim()) return;

    wsRef.current.send(`MSG|${receiver}|${messageText.trim()}`);
    wsRef.current.send(`STOP|${receiver}`);

    setMessageText("");
    setTypingText("");
  };

  /* ================= TYPING HANDLER ================= */
  const handleTyping = () => {
    if (!wsRef.current || !receiver) return;

    wsRef.current.send(`TYPE|${receiver}`);

    if (typingTimeout.current) {
      window.clearTimeout(typingTimeout.current);
    }

    typingTimeout.current = window.setTimeout(() => {
      wsRef.current?.send(`STOP|${receiver}`);
    }, 700);
  };

  /* ================= UI ================= */
  return (
    <div className="app-root">
      <div className="chat-box">
        <h2>Private Chat</h2>

        {/* ===== TOP CONTROLS ===== */}
        <div className="top-controls">
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
            onChange={(e) => {
              setReceiver(e.target.value);
              setReceiverOnline(false);
            }}
          />

          <div className="status">
            <div
              className={`status-dot ${
                receiverOnline ? "online" : "offline"
              }`}
            />
            {receiverOnline ? "Online" : "Offline"}
          </div>
        </div>

        {/* ===== MESSAGES ===== */}
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

        {/* ===== TYPING ===== */}
        <div className="typing">{typingText}</div>

        {/* ===== SEND BAR ===== */}
        <div className="send-bar">
          <input
            placeholder="Type message..."
            value={messageText}
            onChange={(e) => {
              setMessageText(e.target.value);
              handleTyping();
            }}
            disabled={!connected}
            onKeyDown={(e) => {
              if (e.key === "Enter") sendMessage();
            }}
          />
          <button onClick={sendMessage} disabled={!connected}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
