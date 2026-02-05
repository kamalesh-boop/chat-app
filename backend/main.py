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

# ---------------- DATABASE ----------------
conn = sqlite3.connect("chat.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
db_lock = asyncio.Lock()

with conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        receiver TEXT NOT NULL,
        message TEXT NOT NULL,
        read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

# ---------------- PRESENCE ----------------
active_connections: Dict[str, Set[WebSocket]] = {}

# ---------------- HELPERS ----------------
async def send_to_user(username: str, payload: str):
    for ws in active_connections.get(username, set()):
        await ws.send_text(payload)

# ---------------- WEBSOCKET ----------------
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()

    first_connection = username not in active_connections
    active_connections.setdefault(username, set()).add(websocket)

    # ---- PRESENCE SYNC ----
    if first_connection:
        for user, sockets in list(active_connections.items()):
            if user != username:
                for ws in sockets:
                    await ws.send_text(f"STATUS|{username}|online")

    for user in active_connections:
        if user != username:
            await websocket.send_text(f"STATUS|{user}|online")

    try:
        while True:
            data = await websocket.receive_text()

            if "|" not in data:
                continue

            command, rest = data.split("|", 1)

            # ---------- TYPING ----------
            if command == "TYPE":
                receiver = rest
                await send_to_user(receiver, f"TYPING|{username}")

            elif command == "STOP":
                receiver = rest
                await send_to_user(receiver, f"STOP|{username}")

            # ---------- MESSAGE ----------
            elif command == "MSG":
                if "|" not in rest:
                    continue  # malformed

                receiver, message = rest.split("|", 1)

                async with db_lock:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
                        (username, receiver, message)
                    )
                    conn.commit()
                    msg_id = cur.lastrowid

                    cur.execute(
                        "SELECT created_at FROM messages WHERE id = ?",
                        (msg_id,)
                    )
                    timestamp = cur.fetchone()["created_at"]

                payload = f"MSG|{msg_id}|{username}|{receiver}|{message}|{timestamp}"

                await send_to_user(username, payload)
                await send_to_user(receiver, payload)

            # ---------- SEEN ----------
            elif command == "SEEN":
                try:
                    msg_id = int(rest)
                except ValueError:
                    continue

                async with db_lock:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE messages SET read = 1 WHERE id = ?",
                        (msg_id,)
                    )
                    conn.commit()

                    cur.execute(
                        "SELECT sender FROM messages WHERE id = ?",
                        (msg_id,)
                    )
                    row = cur.fetchone()

                if row:
                    await send_to_user(row["sender"], f"READ|{msg_id}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print("WebSocket error:", e)

    finally:
        active_connections[username].discard(websocket)

        if not active_connections[username]:
            del active_connections[username]
            for sockets in list(active_connections.values()):
                for ws in sockets:
                    await ws.send_text(f"STATUS|{username}|offline")
