# StreamingMusical — Credenciales y comandos de ejecución

Referencia rápida para levantar y probar las dos versiones del proyecto (SQL Server y MongoDB) en esta máquina.

## Requisitos ya verificados en esta máquina

- ODBC Driver 18 for SQL Server — instalado.
- SQL Server (instancia default `MSSQLSERVER`, host `VictusMiguel`) — corriendo, modo de autenticación **mixto** (SQL + Windows).
- MongoDB Atlas — credenciales en `mongo_credentials.json` (no confundir con `mongo_credential.json`, sin "s", que no se usa).

Si el servidor `MSSQLSERVER` no arranca solo tras reiniciar Windows:

```powershell
Get-Service MSSQLSERVER
Start-Service MSSQLSERVER
```

---

## Comandos para correr cada versión

Activa el entorno virtual primero en cada terminal:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Versión SQL Server

```powershell
python manage.py runserver 8000
```
→ `http://127.0.0.1:8000/login/`

### Versión MongoDB

```powershell
python manage.py runserver 8001 --settings=core.settings_mongo
```
→ `http://127.0.0.1:8001/mongo/login/`

**Importante:** el flag `--settings=core.settings_mongo` es obligatorio para la versión Mongo. Sin él, el servidor arranca pero usa los templates de la versión SQL y falla al navegar (error `NoReverseMatch`). Revisa siempre la URL antes de loguearte — ambas pestañas se ven casi idénticas, pero solo una tiene `/mongo/` en la ruta.

---

## Credenciales de prueba

### SQL Server (login por **nombre corto**, `http://127.0.0.1:8000/login/`)

| Nombre | Password | Rol |
|---|---|---|
| `Carlos` | `pass123` | Usuario |
| `Ana` | `ana456` | Usuario |
| `Luis` | `luis789` | Usuario |
| `María` | `maria321` | Usuario |
| `Jorge` | `jorge654` | Usuario |
| `Laura` | `laura987` | Artista |
| `Diego` | `diego147` | Artista |
| `Sofía` | `sofia258` | Artista |
| `Pablo` | `pablo369` | Artista |
| `Valentina` | `vale741` | Artista |

No existe cuenta de administrador (ningún registro se llama "admin" en los datos semilla).

### MongoDB (login por **correo electrónico**, `http://127.0.0.1:8001/mongo/login/`)

| Email | Password | Rol |
|---|---|---|
| `carlos.mendoza@email.com` | `pass123` | Usuario |
| `ana.gomez@email.com` | `ana456` | Usuario |
| `luis.ramirez@email.com` | `luis789` | Usuario |
| `jorge_p` → email real: `jorge.perez@email.com` | `jorge123` | Usuario |
| `maria.fernandez@email.com` | `maria123` | Usuario |
| `sofia.vargas@email.com` | `sofia123` | Usuario |
| `diego.castro@email.com` | `diego147` | Artista |
| `laura.sanchez@email.com` | `laura987` | Artista |
| `sofia.rojas@email.com` | `sofirock123` | Artista |
| `pablo.ortiz@email.com` | `pablosound123` | Artista |
| `valentina.navarro@email.com` | `valentinaflow123` | Artista |
| `camilo.soto@email.com` | `camilosoto123` | Artista |
| `admin` | `admin` | Administrador (hardcodeado, sin colección propia) |

---

## Verificar datos directamente en cada base de datos

Útil para confirmar que un CRUD desde la web realmente se guardó, sin depender solo del mensaje de éxito en pantalla.

### SQL Server

```powershell
python -c "import pyodbc; conn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=VictusMiguel;DATABASE=StreamingMusical;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;'); cur = conn.cursor(); cur.execute('SELECT idPlaylist, nombrePlaylist, descripcion FROM Playlists.Playlist'); [print(r.idPlaylist, r.nombrePlaylist, r.descripcion) for r in cur.fetchall()]"
```

*(Alternativa visual: SQL Server Management Studio, conectar a `VictusMiguel` con login `DMA_SA` / `Password123!`.)*

### MongoDB

```powershell
python -c "import json; from pymongo import MongoClient; creds=json.load(open('mongo_credentials.json',encoding='utf-8')); db=MongoClient(creds['uri'])[creds['database']]; [print(p['_id'], p['nombrePlaylist'], p.get('descripcion')) for p in db['playlists'].find()]"
```

*(Alternativa visual: [cloud.mongodb.com](https://cloud.mongodb.com) → cluster `Cluster0` → "Browse Collections" → base `StreamingMusicalNoSQL`, o MongoDB Compass con la misma URI.)*

---

## Notas de configuración (por si hay que reinstalar)

- `core/settings.py` usa el driver `ODBC Driver 18 for SQL Server` con `Encrypt=yes;TrustServerCertificate=yes;`.
- El login SQL `DMA_SA` solo tiene permisos DML (`SELECT/INSERT/UPDATE/DELETE/EXECUTE`) por diseño de seguridad del script `sql/fase3_seguridad_logica.sql`. Si hace falta correr `python manage.py migrate` (tablas propias de Django: sesiones, admin, `TokenRecuperacion`), hay que agregarlo temporalmente al rol `db_ddladmin` y quitarlo después:
  ```sql
  ALTER ROLE db_ddladmin ADD MEMBER DMA_SA;   -- antes de migrate
  ALTER ROLE db_ddladmin DROP MEMBER DMA_SA;  -- después de migrate
  ```
- El schema completo de SQL Server (tablas, datos semilla, procedimientos, trigger) está en `sql/fase3_seguridad_logica.sql`.
- El schema de MongoDB es denormalizado (canciones embebidas en álbumes/playlists); el detalle de esa arquitectura está documentado en la memoria persistente del asistente para esta sesión.
