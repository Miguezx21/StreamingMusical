# streaming_mongo/db.py
# -----------------------------------------------------------------------
# Conexión a MongoDB Atlas leyendo credenciales desde archivo JSON
# Feedback Fase 6: "Evidencia de Conexión a la BD NoSQL desde Python"
# -----------------------------------------------------------------------
import json
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Ruta al archivo de credenciales JSON
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'mongo_credentials.json')

_client = None
_db     = None


def _load_credentials():
    """Lee las credenciales desde el archivo JSON externo."""
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales: {CREDENTIALS_PATH}\n"
            "Crea 'mongo_credentials.json' en la raíz del proyecto."
        )
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_db():
    """
    Retorna la instancia de la base de datos MongoDB.
    Usa patrón Singleton — una sola conexión por proceso.
    """
    global _client, _db
    if _db is not None:
        return _db

    creds = _load_credentials()
    uri      = creds.get('uri')
    db_name  = creds.get('database', 'StreamingMusicalNoSQL')

    if not uri:
        raise ValueError("El archivo JSON no contiene el campo 'uri'.")

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Verificar conexión activa
        _client.admin.command('ping')
        _db = _client[db_name]
        print(f"[OK] Conectado a MongoDB Atlas - base de datos: {db_name}")
    except ConnectionFailure as e:
        raise ConnectionFailure(f"No se pudo conectar a MongoDB Atlas: {e}")

    return _db


# -----------------------------------------------------------------------
# Helpers de colecciones — acceso directo y limpio desde las vistas
# -----------------------------------------------------------------------
def col_artistas():
    return get_db()['artistas']

def col_albumes():
    return get_db()['albumes']

def col_usuarios():
    return get_db()['usuarios']

def col_playlists():
    return get_db()['playlists']

def col_reproducciones():
    return get_db()['reproducciones']

def col_tokens():
    return get_db()['tokens_recuperacion']