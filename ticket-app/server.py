import json
import sqlite3
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
            """
        )
        conn.commit()


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class TicketHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/registros":
            try:
                with get_db_connection() as conn:
                    registros = conn.execute(
                        "SELECT id, nombre, descripcion, fecha FROM registros ORDER BY id DESC"
                    ).fetchall()

                return json_response(self, 200, [dict(row) for row in registros])
            except Exception as exc:
                return json_response(self, 500, {"error": str(exc)})

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/registros":
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                payload = json.loads(raw_body.decode("utf-8") or "{}")

                nombre = str(payload.get("nombre", "")).strip()
                descripcion = str(payload.get("descripcion", "")).strip()

                if not nombre or not descripcion:
                    return json_response(self, 400, {"error": "Nombre y descripción son obligatorios"})

                fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                with get_db_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO registros (nombre, descripcion, fecha) VALUES (?, ?, ?)",
                        (nombre, descripcion, fecha),
                    )
                    conn.commit()
                    registro_id = cursor.lastrowid
                    registro = conn.execute(
                        "SELECT id, nombre, descripcion, fecha FROM registros WHERE id = ?",
                        (registro_id,),
                    ).fetchone()

                return json_response(self, 201, dict(registro))
            except Exception as exc:
                return json_response(self, 500, {"error": str(exc)})

        return json_response(self, 404, {"error": "Ruta no encontrada"})

    def do_DELETE(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/registros":
            try:
                params = parse_qs(parsed.query)
                registro_id = params.get("id", [None])[0]

                if registro_id is None:
                    return json_response(self, 400, {"error": "Falta el parámetro id"})

                with get_db_connection() as conn:
                    cursor = conn.execute("DELETE FROM registros WHERE id = ?", (int(registro_id),))
                    conn.commit()

                return json_response(self, 200, {"ok": True, "deleted": cursor.rowcount})
            except Exception as exc:
                return json_response(self, 500, {"error": str(exc)})

        return json_response(self, 404, {"error": "Ruta no encontrada"})


if __name__ == "__main__":
    init_db()
    port = 8000
    print(f"Servidor de tickets iniciado en http://127.0.0.1:{port}")
    print(f"Base de datos: {DB_PATH}")
    server = ThreadingHTTPServer(("127.0.0.1", port), TicketHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()
