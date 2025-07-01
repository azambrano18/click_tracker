import os
import logging
import hashlib
import psycopg2
from datetime import datetime
from pytz import timezone
from flask import Flask, request, redirect

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")


def generar_token(remitente: str, destinatario: str, url: str, secreto: str = "clave-secreta") -> str:
    base = f"{remitente}-{destinatario}-{url}-{secreto}"
    return hashlib.sha256(base.encode()).hexdigest()


@app.route("/click")
def redirigir_click():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    url_destino = request.args.get("url")
    token_recibido = request.args.get("token")

    if not all([remitente, destinatario, url_destino, token_recibido]):
        return "<h3>Faltan parámetros requeridos</h3>", 400

    # Validar token
    token_esperado = generar_token(remitente, destinatario, url_destino)
    if token_recibido != token_esperado:
        return "<h3>Token inválido</h3>", 403

    tz_scl = timezone("America/Santiago")
    fecha_click = datetime.now(tz_scl)

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Buscar si existe el envío con ese token
                cur.execute("""
                    SELECT id FROM envios_clicks
                    WHERE token = %s
                """, (token_recibido,))
                existe = cur.fetchone()

                if existe:
                    # Actualizar contador y timestamp
                    cur.execute("""
                        UPDATE envios_clicks
                        SET
                            clicks_count = COALESCE(clicks_count,0) + 1,
                            last_click_at = %s,
                            url_destino = %s
                        WHERE id = %s
                    """, (
                        fecha_click,
                        url_destino,
                        existe[0]
                    ))
                    logging.info(f"[CLICK] Contador incrementado para token {token_recibido}")
                else:
                    logging.warning(f"[CLICK] No se encontró envío con token {token_recibido}")

    except Exception:
        logging.exception("[CLICK] Error al registrar clic")

    return redirect(url_destino)


@app.route("/")
def index():
    return "<h3>Click Tracker activo - Proyecto ENVÍOS</h3>"


@app.route("/status")
def status():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}, 200
    except:
        return {"status": "error"}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask click_tracker iniciado")
    app.run(host="0.0.0.0", port=port)