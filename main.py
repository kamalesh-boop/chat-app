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
    message TEXT
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

    # 🔹 Send previous chat history
    cursor.execute("""
        SELECT sender, receiver, message FROM messages
        WHERE sender = ? OR receiver = ?
    """, (username, username))

    for s, r, m in cursor.fetchall():
        await websocket.send_text(f"{s} → {r}: {m}")

    try:
        while True:
            data = await websocket.receive_text()
            parts = data.split("|")
            action = parts[0]

            # -------- TYPING INDICATOR --------
            if action == "TYPE":
                receiver = parts[1]
                if receiver in active_connections:
                    await active_connections[receiver].send_text(
                        f"TYPING|{username}"
                    )

            elif action == "STOP":
                receiver = parts[1]
                if receiver in active_connections:
                    await active_connections[receiver].send_text(
                        f"STOP|{username}"
                    )

            # -------- NORMAL MESSAGE --------
            elif action == "MSG":
                receiver = parts[1]
                message = parts[2]

                cursor.execute(
                    "INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
                    (username, receiver, message)
                )
                conn.commit()

                formatted = f"{username} → {receiver}: {message}"

                # send to receiver
                if receiver in active_connections:
                    await active_connections[receiver].send_text(formatted)

                # send back to sender
                await websocket.send_text(formatted)

    except:
        if username in active_connections:
            del active_connections[username]
