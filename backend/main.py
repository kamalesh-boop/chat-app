from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import sqlite3
import asyncio

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for demo / academic use
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
    read INTEGER DEFAULT 0
)
""")
conn.commit()

db_lock = asyncio.Lock()

# ---------------- ACTIVE CONNECTIONS ----------------
active_connections: Dict[str, WebSocket] = {}

# ---------------- WEBSOCKET ----------------
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections[username] = websocket

    # =====================================================
    # PRESENCE SYNC
    # =====================================================

    # Notify others I'm online
    for user, ws in active_connections.items():
        if user != username:
            await ws.send_text(f"STATUS|{username}|online")

    # Tell me who is already online
    for user in active_connections:
        if user != username:
            await websocket.send_text(f"STATUS|{user}|online")

    # =====================================================
    # SEND CHAT HISTORY
    # =====================================================
    async with db_lock:
        cursor.execute("""
            SELECT id, sender, receiver, message, read
            FROM messages
            WHERE sender = ? OR receiver = ?
            ORDER BY id ASC
        """, (username, username))
        rows = cursor.fetchall()

    for msg_id, sender, receiver, message, read in rows:
        status = "✔✔" if read else "✔"
        if sender == username:
            await websocket.send_text(
                f"MSG|{msg_id}|{sender}|{receiver}|{message}|{status}"
            )
        else:
            await websocket.send_text(
                f"MSG|{msg_id}|{sender}|{receiver}|{message}|"
            )

    # =====================================================
    # MAIN LOOP
    # =====================================================
    try:
        while True:
            data = await websocket.receive_text()
            parts = data.split("|")
            action = parts[0]

            # ---------------- TYPING ----------------
            if action == "TYPE" and len(parts) >= 2:
                receiver = parts[1]
                if receiver in active_connections:
                    await active_connections[receiver].send_text(
                        f"TYPING|{username}"
                    )

            elif action == "STOP" and len(parts) >= 2:
                receiver = parts[1]
                if receiver in active_connections:
                    await active_connections[receiver].send_text(
                        f"STOP|{username}"
                    )

            # ---------------- MESSAGE ----------------
            elif action == "MSG" and len(parts) >= 3:
                receiver = parts[1]
                message = parts[2]

                async with db_lock:
                    cursor.execute(
                        "INSERT INTO messages (sender, receiver, message, read) VALUES (?, ?, ?, 0)",
                        (username, receiver, message)
                    )
                    conn.commit()
                    msg_id = cursor.lastrowid

                formatted = f"MSG|{msg_id}|{username}|{receiver}|{message}|✔"

                # Send to receiver (DELIVERED, not read)
                if receiver in active_connections:
                    await active_connections[receiver].send_text(formatted)

                # Always send to sender
                await websocket.send_text(formatted)

            # ---------------- SEEN (IMPORTANT) ----------------
            elif action == "SEEN" and len(parts) >= 2:
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
                    if sender in active_connections:
                        await active_connections[sender].send_text(
                            f"READ|{msg_id}"
                        )

    except WebSocketDisconnect:
        pass
    finally:
        # =====================================================
        # CLEANUP & OFFLINE BROADCAST
        # =====================================================
        if username in active_connections:
            del active_connections[username]

            for ws in active_connections.values():
                await ws.send_text(f"STATUS|{username}|offline")
