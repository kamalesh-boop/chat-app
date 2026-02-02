from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import sqlite3

app = FastAPI()

# ---------------- DATABASE ----------------
conn = sqlite3.connect("chat.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    receiver TEXT,
    message TEXT,
    read INTEGER DEFAULT 0
)
""")
conn.commit()

# ---------------- CONNECTIONS ----------------
active_connections = {}  # username -> websocket

@app.get("/")
async def get():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections[username] = websocket

    # -------- SEND CHAT HISTORY --------
    cursor.execute("""
        SELECT id, sender, receiver, message, read
        FROM messages
        WHERE sender = ? OR receiver = ?
        ORDER BY id
    """, (username, username))

    for msg_id, sender, receiver, message, read in cursor.fetchall():
        status = "✔✔" if read else "✔"
        if sender == username:
            await websocket.send_text(
                f"MSG|{msg_id}|{sender}|{receiver}|{message}|{status}"
            )
        else:
            await websocket.send_text(
                f"MSG|{msg_id}|{sender}|{receiver}|{message}|"
            )

    # -------- MARK UNREAD AS READ ON CONNECT --------
    cursor.execute("""
        SELECT id, sender FROM messages
        WHERE receiver = ? AND read = 0
    """, (username,))
    unread_messages = cursor.fetchall()

    if unread_messages:
        cursor.execute("""
            UPDATE messages SET read = 1
            WHERE receiver = ? AND read = 0
        """, (username,))
        conn.commit()

        for msg_id, sender in unread_messages:
            if sender in active_connections:
                await active_connections[sender].send_text(f"READ|{msg_id}")

    try:
        while True:
            data = await websocket.receive_text()
            parts = data.split("|")

            if not parts:
                continue

            action = parts[0]

            # -------- TYPING --------
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

            # -------- MESSAGE --------
            elif action == "MSG" and len(parts) >= 3:
                receiver = parts[1]
                message = parts[2]

                cursor.execute(
                    "INSERT INTO messages (sender, receiver, message, read) VALUES (?, ?, ?, 0)",
                    (username, receiver, message)
                )
                conn.commit()

                msg_id = cursor.lastrowid
                formatted = f"MSG|{msg_id}|{username}|{receiver}|{message}|✔"

                # Send to receiver
                if receiver in active_connections:
                    await active_connections[receiver].send_text(formatted)

                    # Mark as read immediately
                    cursor.execute(
                        "UPDATE messages SET read = 1 WHERE id = ? AND read = 0",
                        (msg_id,)
                    )
                    conn.commit()

                    # Notify sender
                    await websocket.send_text(f"READ|{msg_id}")

                # Always send message to sender
                await websocket.send_text(formatted)

    except:
        if username in active_connections:
            del active_connections[username]
