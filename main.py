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

                # 🔹 Mark messages as READ when user is online
                cursor.execute("""
                    UPDATE messages
                    SET read = 1
                    WHERE receiver = ? AND read = 0
                """, (username,))
                conn.commit()


                formatted = f"{username} → {receiver}: {message} ✔"

                # send to receiver
                if receiver in active_connections:
                    await active_connections[receiver].send_text(formatted)
                    await websocket.send_text(f"READ|{receiver}")


                # send back to sender
                await websocket.send_text(formatted)

    except:
        if username in active_connections:
            del active_connections[username]
