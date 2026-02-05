import { useEffect, useRef, useState } from "react";
import "./index.css";

const WS_BASE = "wss://chat-backend-fxwq.onrender.com";

type MsgStatus = "sent" | "seen";

type Msg = {
  id: number;
  text: string;
  sender: string;
  status: MsgStatus;
  timestamp: string;
};

export default function App() {
  const [username, setUsername] = useState("");
  const [receiver, setReceiver] = useState("");
  const [connected, setConnected] = useState(false);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [messageText, setMessageText] = useState("");
  const [typingText, setTypingText] = useState("");
  const [onlineUsers, setOnlineUsers] = useState<Set<string>>(new Set());

  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeout = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const formatTime = (ts: string) =>
    new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  // ---------- CONNECT ----------
  const connect = () => {
    if (!username || connected) return;

    const ws = new WebSocket(`${WS_BASE}/ws/${username}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onclose = () => {
      setConnected(false);
      setTypingText("");
      setOnlineUsers(new Set());
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      const data = event.data as string;

      if (data.startsWith("STATUS|")) {
        const [, user, state] = data.split("|");
        setOnlineUsers((prev) => {
          const next = new Set(prev);
          state === "online" ? next.add(user) : next.delete(user);
          return next;
        });
        return;
      }

      if (data.startsWith("READ|")) {
        const id = Number(data.split("|")[1]);
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, status: "seen" } : m))
        );
        return;
      }

      if (data.startsWith("TYPING|")) {
        const user = data.split("|")[1];
        if (user === receiver) setTypingText(`${user} is typing...`);
        return;
      }

      if (data.startsWith("STOP|")) {
        setTypingText("");
        return;
      }

      if (data.startsWith("MSG|")) {
        const [, id, sender, , rest] = data.split("|", 5);
        const [text, timestamp] = rest.split("|", 2);
        const msgId = Number(id);

        setMessages((prev) =>
          prev.some((m) => m.id === msgId)
            ? prev
            : [
                ...prev,
                {
                  id: msgId,
                  sender,
                  text,
                  timestamp,
                  status: sender === username ? "sent" : "seen",
                },
              ]
        );

        if (sender !== username) {
          wsRef.current?.send(`SEEN|${msgId}`);
        }
      }
    };
  };

  const sendMessage = () => {
    if (!wsRef.current || !receiver || !messageText.trim()) return;
    wsRef.current.send(`MSG|${receiver}|${messageText}`);
    wsRef.current.send(`STOP|${receiver}`);
    setMessageText("");
  };

  const handleTyping = () => {
    if (!wsRef.current || !receiver) return;

    wsRef.current.send(`TYPE|${receiver}`);
    if (typingTimeout.current) clearTimeout(typingTimeout.current);

    typingTimeout.current = window.setTimeout(
      () => wsRef.current?.send(`STOP|${receiver}`),
      800
    );
  };

  const isOnline = onlineUsers.has(receiver);

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

        <div className="status">
          <span className={`status-dot ${isOnline ? "online" : "offline"}`} />
          {receiver ? (isOnline ? "Online" : "Offline") : "—"}
        </div>

        <div className="messages">
          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.sender === username ? "me" : "other"}`}>
              <div className="bubble">
                <div className="text">{m.text}</div>
                <div className="meta">
                  <span className="time">{formatTime(m.timestamp)}</span>
                  {m.sender === username && (
                    <span className={`tick ${m.status === "seen" ? "seen" : ""}`}>
                      {m.status === "seen" ? "✔✔" : "✔"}
                    </span>
                  )}
                </div>
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
