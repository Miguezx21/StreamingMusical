# core/settings_mongo.py
# -----------------------------------------------------------------------
# Settings para la versión MongoDB del proyecto
# Uso: python manage.py runserver --settings=core.settings_mongo
# -----------------------------------------------------------------------
from .settings import *  # Hereda todo del settings original
 
# -----------------------------------------------------------------------
# Base de datos — sin SQL Server
# MongoDB se conecta via PyMongo en streaming_mongo/db.py
# Django necesita una DB mínima para sesiones y tokens
# -----------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_mongo_sessions.sqlite3',
    }
}
 
# -----------------------------------------------------------------------
# Apps instaladas
# -----------------------------------------------------------------------
# core/urls.py enruta SIEMPRE ambas apps ('' -> streaming, 'mongo/' ->
# streaming_mongo), así que ambas deben estar registradas aunque en este
# modo solo se usen las vistas de streaming_mongo (PyMongo). Los modelos
# de streaming.models son managed=False y apuntan a SQL Server: no se
# consultan a menos que entres por la ruta '/', así que no afectan a la
# sesión sqlite de este modo.
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'streaming',
    'streaming_mongo',
]
 
# -----------------------------------------------------------------------
# Templates — copias propias de streaming_mongo/templates/streaming/
# (idénticas a las de streaming/, pero con {% url %} apuntando al
# namespace 'mongo'; ver streaming_mongo/urls.py). Django no puede
# resolver un {% url 'nombre' %} sin namespace hacia la app correcta
# cuando ambas apps registran el mismo nombre de vista, así que no se
# pueden compartir los .html originales sin modificarlos.
# -----------------------------------------------------------------------
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'streaming_mongo' / 'templates']
 
