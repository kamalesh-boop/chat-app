import { useEffect, useRef, useState } from "react";
import "./index.css";

const WS_BASE = "wss://chat-backend-fxwq.onrender.com";

type MsgStatus = "sent" | "seen";

type Msg = {
  id: number;
  text: string;
  sender: string;
  status: MsgStatus;
};

export default function App() {
  // ---------------- STATE ----------------
  const [username, setUsername] = useState("");
  const [receiver, setReceiver] = useState("");
  const [connected, setConnected] = useState(false);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [messageText, setMessageText] = useState("");
  const [typingText, setTypingText] = useState("");

  // ---------------- REFS ----------------
  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeout = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // ---------------- AUTO SCROLL ----------------
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ---------------- CONNECT ----------------
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
    };

    ws.onmessage = (event) => {
      const data = event.data;

      // ================= READ RECEIPT =================
      // Backend → READ|messageId
      if (data.startsWith("READ|")) {
        const id = Number(data.split("|")[1]);

        setMessages((prev) =>
          prev.map((m) =>
            m.id === id ? { ...m, status: "seen" } : m
          )
        );
        return;
      }

      // ================= TYPING =================
      if (data.startsWith("TYPING|")) {
        const user = data.split("|")[1];
        setTypingText(`${user} is typing...`);
        return;
      }

      if (data.startsWith("STOP|")) {
        setTypingText("");
        return;
      }

      // ================= MESSAGE =================
      // Backend → MSG|id|sender|receiver|text|✔
      if (data.startsWith("MSG|")) {
        const [, id, sender, , text] = data.split("|");
        const msgId = Number(id);

        setMessages((prev) => {
          // Prevent duplicate messages
          if (prev.some((m) => m.id === msgId)) return prev;

          return [
            ...prev,
            {
              id: msgId,
              sender,
              text,
              status: "sent", // always start as SENT
            },
          ];
        });

        // 🔥 CRITICAL STEP:
        // If I am the RECEIVER, notify backend that I have SEEN this message
        if (sender !== username) {
          wsRef.current?.send(`SEEN|${msgId}`);
        }
      }
    };
  };

  // ---------------- SEND MESSAGE ----------------
  const sendMessage = () => {
    if (!wsRef.current || !receiver || !messageText) return;

    wsRef.current.send(`MSG|${receiver}|${messageText}`);
    wsRef.current.send(`STOP|${receiver}`);
    setMessageText("");
  };

  // ---------------- TYPING HANDLER ----------------
  const handleTyping = () => {
    if (!wsRef.current || !receiver) return;

    wsRef.current.send(`TYPE|${receiver}`);

    if (typingTimeout.current) {
      window.clearTimeout(typingTimeout.current);
    }

    typingTimeout.current = window.setTimeout(() => {
      wsRef.current?.send(`STOP|${receiver}`);
    }, 800);
  };

  // ---------------- UI ----------------
  return (
    <div className="app-root">
      <div className="chat-box">
        <h2>Private Chat</h2>

        {/* USERNAME */}
        <input
          placeholder="Your username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={connected}
        />

        <button onClick={connect} disabled={connected}>
          {connected ? "Connected" : "Join"}
        </button>

        {/* RECEIVER */}
        <input
          placeholder="Chat with (username)"
          value={receiver}
          onChange={(e) => setReceiver(e.target.value)}
        />

        {/* MESSAGES */}
        <div className="messages">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`msg ${m.sender === username ? "me" : "other"}`}
            >
              <div className="bubble">
                {m.text}

                {/* TICK */}
                {m.sender === username && (
                  <span
                    className={`tick ${
                      m.status === "seen" ? "seen" : ""
                    }`}
                  >
                    ✔✔
                  </span>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* TYPING INDICATOR */}
        <div className="typing">{typingText}</div>

        {/* MESSAGE INPUT */}
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
