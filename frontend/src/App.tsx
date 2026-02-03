import { useEffect, useRef, useState } from "react";
import "./index.css";

const WS_BASE = "wss://chat-backend-fxwq.onrender.com";

type Msg = {
  id: number;
  text: string;
  sender: string;
  status: "✔" | "✔✔";
};

export default function App() {
  const [username, setUsername] = useState("");
  const [receiver, setReceiver] = useState("");
  const [connected, setConnected] = useState(false);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [messageText, setMessageText] = useState("");

  const [typingText, setTypingText] = useState("");
  const [onlineStatus, setOnlineStatus] = useState<"online" | "offline">(
    "offline"
  );

  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeout = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  /* ---------------- AUTO SCROLL ---------------- */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ---------------- CONNECT ---------------- */
  const connect = () => {
    if (!username.trim()) return;

    const ws = new WebSocket(`${WS_BASE}/ws/${username}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      setTypingText("");
      setOnlineStatus("offline");
    };

    ws.onmessage = (event) => {
      const data: string = event.data;

      /* ---------- STATUS ---------- */
      if (data.startsWith("STATUS|")) {
        const [, user, state] = data.split("|");
        if (user === receiver) {
          setOnlineStatus(state === "online" ? "online" : "offline");
        }
        return;
      }

      /* ---------- READ RECEIPT ---------- */
      if (data.startsWith("READ|")) {
        const id = Number(data.split("|")[1]);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id ? { ...m, status: "✔✔" } : m
          )
        );
        return;
      }

      /* ---------- TYPING ---------- */
      if (data.startsWith("TYPING|")) {
        const sender = data.split("|")[1];
        if (sender === receiver) {
          setTypingText(`${sender} is typing…`);
        }
        return;
      }

      if (data.startsWith("STOP|")) {
        const sender = data.split("|")[1];
        if (sender === receiver) {
          setTypingText("");
        }
        return;
      }

      /* ---------- MESSAGE ---------- */
      if (data.startsWith("MSG|")) {
        const [, id, sender, , text, status] = data.split("|");
        const msgId = Number(id);

        setMessages((prev) => {
          if (prev.some((m) => m.id === msgId)) return prev;
          return [
            ...prev,
            {
              id: msgId,
              sender,
              text,
              status: status === "✔✔" ? "✔✔" : "✔",
            },
          ];
        });
      }
    };
  };

  /* ---------------- SEND MESSAGE ---------------- */
  const sendMessage = () => {
    if (!wsRef.current || !receiver.trim() || !messageText.trim()) return;

    wsRef.current.send(`MSG|${receiver}|${messageText}`);
    wsRef.current.send(`STOP|${receiver}`);
    setMessageText("");
  };

  /* ---------------- TYPING HANDLER ---------------- */
  const handleTyping = () => {
    if (!wsRef.current || !receiver.trim()) return;

    wsRef.current.send(`TYPE|${receiver}`);

    if (typingTimeout.current) {
      window.clearTimeout(typingTimeout.current);
    }

    typingTimeout.current = window.setTimeout(() => {
      wsRef.current?.send(`STOP|${receiver}`);
    }, 800);
  };

  /* ---------------- UI ---------------- */
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
          onChange={(e) => {
            setReceiver(e.target.value);
            setOnlineStatus("offline");
            setTypingText("");
          }}
        />

        <div className={`status ${onlineStatus}`}>
          {onlineStatus === "online" ? "🟢 Online" : "🔴 Offline"}
        </div>

        <div className="messages">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`msg ${m.sender === username ? "me" : "other"}`}
            >
              <div className="bubble">
                {m.text}
                {m.sender === username && (
                  <span className="tick">{m.status}</span>
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
