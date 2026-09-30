import os
import sqlite3
import datetime
from flask import Flask, jsonify, request, g

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "examer.db")

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS subjects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT, name TEXT, date TEXT, conf INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            client TEXT PRIMARY KEY, hours REAL)""")


init_db()


def client():
    # each browser sends its own id, so every user sees only their own data
    return request.headers.get("X-Client", "anon")[:64]


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.get("/api/subjects")
def list_subjects():
    rows = db().execute(
        "SELECT id, name, date, conf FROM subjects WHERE client=?", (client(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/subjects")
def add_subject():
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()[:60]
    try:
        datetime.date.fromisoformat(str(d.get("date", "")))
        conf = int(d.get("conf"))
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid date and confidence (1-5)."), 400
    if not name or not 1 <= conf <= 5:
        return jsonify(error="Enter a subject name and confidence (1-5)."), 400
    cur = db().execute(
        "INSERT INTO subjects(client, name, date, conf) VALUES(?,?,?,?)",
        (client(), name, d["date"], conf),
    )
    db().commit()
    return jsonify(id=cur.lastrowid, name=name, date=d["date"], conf=conf), 201


@app.delete("/api/subjects/<int:sid>")
def delete_subject(sid):
    db().execute("DELETE FROM subjects WHERE id=? AND client=?", (sid, client()))
    db().commit()
    return "", 204


@app.get("/api/settings")
def get_settings():
    r = db().execute("SELECT hours FROM settings WHERE client=?", (client(),)).fetchone()
    return jsonify(hours=r["hours"] if r else 4)


@app.put("/api/settings")
def put_settings():
    d = request.get_json(silent=True) or {}
    try:
        h = min(16, max(1, float(d.get("hours"))))
    except (TypeError, ValueError):
        return jsonify(error="Hours must be a number."), 400
    db().execute(
        "INSERT INTO settings(client, hours) VALUES(?,?) "
        "ON CONFLICT(client) DO UPDATE SET hours=excluded.hours",
        (client(), h),
    )
    db().commit()
    return jsonify(hours=h)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nExam ER is running. Open http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
