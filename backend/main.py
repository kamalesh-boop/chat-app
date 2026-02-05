from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set
import sqlite3
import asyncio

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DATABASE (FIXED) ----------------
conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    message TEXT NOT NULL,
    read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

db_lock = asyncio.Lock()

# ---------------- PRESENCE ----------------
active_connections: Dict[str, Set[WebSocket]] = {}

# ---------------- WEBSOCKET ----------------
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()

    first_connection = False
    if username not in active_connections:
        active_connections[username] = set()
        first_connection = True

    active_connections[username].add(websocket)

    # ---- ONLINE SYNC ----
    if first_connection:
        for user, sockets in active_connections.items():
            if user != username:
                for ws in sockets:
                    await ws.send_text(f"STATUS|{username}|online")

    for user in active_connections:
        if user != username:
            await websocket.send_text(f"STATUS|{user}|online")

    try:
        while True:
            data = await websocket.receive_text()

            # ✅ SAFE SPLIT
            parts = data.split("|", 2)
            action = parts[0]

            # ---------- TYPING ----------
            if action == "TYPE" and len(parts) == 2:
                receiver = parts[1]
                if receiver in active_connections:
                    for ws in active_connections[receiver]:
                        await ws.send_text(f"TYPING|{username}")

            elif action == "STOP" and len(parts) == 2:
                receiver = parts[1]
                if receiver in active_connections:
                    for ws in active_connections[receiver]:
                        await ws.send_text(f"STOP|{username}")

            # ---------- MESSAGE ----------
            elif action == "MSG" and len(parts) == 3:
                receiver, message = parts[1], parts[2]

                async with db_lock:
                    cursor.execute(
                        "INSERT INTO messages (sender, receiver, message, read) VALUES (?, ?, ?, 0)",
                        (username, receiver, message)
                    )
                    conn.commit()
                    msg_id = cursor.lastrowid

                    cursor.execute(
                        "SELECT created_at FROM messages WHERE id = ?",
                        (msg_id,)
                    )
                    timestamp = cursor.fetchone()[0]

                payload = f"MSG|{msg_id}|{username}|{receiver}|{message}|{timestamp}"

                # Send to sender (all tabs)
                for ws in active_connections.get(username, []):
                    await ws.send_text(payload)

                # Send to receiver if online
                for ws in active_connections.get(receiver, []):
                    await ws.send_text(payload)

            # ---------- SEEN ----------
            elif action == "SEEN" and len(parts) == 2:
                msg_id = int(parts[1])

                async with db_lock:
                    cursor.execute(
                        "UPDATE messages SET read = 1 WHERE id = ?",
                        (msg_id,)
                    )
                    conn.commit()

                    cursor.execute(
                        "SELECT sender FROM messages WHERE id = ?",
                        (msg_id,)
                    )
                    row = cursor.fetchone()

                if row:
                    sender = row[0]
                    for ws in active_connections.get(sender, []):
                        await ws.send_text(f"READ|{msg_id}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 🔥 NEVER CRASH THE SOCKET SILENTLY
        print("WebSocket error:", e)

    finally:
        # ---------- CLEANUP ----------
        active_connections[username].discard(websocket)

        if not active_connections[username]:
            del active_connections[username]
            for sockets in active_connections.values():
                for ws in sockets:
                    await ws.send_text(f"STATUS|{username}|offline")
