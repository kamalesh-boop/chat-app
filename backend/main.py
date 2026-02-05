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

# ---------------- PRESENCE (MULTI-TAB SAFE) ----------------
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

    # ---------- PRESENCE SYNC ----------
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
            parts = data.split("|")
            action = parts[0]

            # ---------- TYPING ----------
            if action == "TYPE":
                receiver = parts[1]
                if receiver in active_connections:
                    for ws in active_connections[receiver]:
                        await ws.send_text(f"TYPING|{username}")

            elif action == "STOP":
                receiver = parts[1]
                if receiver in active_connections:
                    for ws in active_connections[receiver]:
                        await ws.send_text(f"STOP|{username}")

            # ---------- MESSAGE ----------
            elif action == "MSG":
                receiver = parts[1]
                message = parts[2]

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
                for ws in active_connections[username]:
                    await ws.send_text(payload)

                # Send to receiver if online
                if receiver in active_connections:
                    for ws in active_connections[receiver]:
                        await ws.send_text(payload)

            # ---------- SEEN ----------
            elif action == "SEEN":
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
                    sender = cursor.fetchone()[0]

                if sender in active_connections:
                    for ws in active_connections[sender]:
                        await ws.send_text(f"READ|{msg_id}")

    except WebSocketDisconnect:
        pass
    finally:
        # ---------- CLEANUP ----------
        active_connections[username].remove(websocket)

        if not active_connections[username]:
            del active_connections[username]
            for sockets in active_connections.values():
                for ws in sockets:
                    await ws.send_text(f"STATUS|{username}|offline")
