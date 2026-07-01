# streaming_mongo/views.py
# -----------------------------------------------------------------------
# Vistas equivalentes a streaming/views.py pero usando PyMongo (MongoDB
# Atlas) en vez del ORM de Django sobre SQL Server.
#
# El schema real en Atlas es denormalizado/embebido:
#   usuarios   -> perfil{}, suscripcion{} embebidos, login por email
#   artistas   -> persona{} embebido, login por email (agregado en migración)
#   albumes    -> canciones[] embebidas (cada una con "pista")
#   playlists  -> canciones[] embebidas (duplicadas de albumes, con
#                 "origenId" = "<idAlbum>:<pista>" que enlaza a la canción
#                 original en su álbum)
#   reproducciones -> registros de escucha (denormalizados)
#
# Como no existe una colección de "canciones" independiente, una canción
# se identifica con la clave compuesta "<idAlbum>:<pista>".
#
# Los templates son los MISMOS que usa streaming/ (ver
# core/settings_mongo.py TEMPLATES[0]['DIRS']) y esperan nombres de
# atributo estilo SQL (idcancion, nombrecancion, idalbum.nombrealbum,
# etc.). Por eso las funciones _*_ctx de este módulo traducen los
# documentos de Mongo a diccionarios con esas claves exactas.
# -----------------------------------------------------------------------
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from bson import ObjectId
from bson.errors import InvalidId
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone

from streaming.forms import (
    AlbumForm,
    CancionForm,
    PlaylistForm,
    RecuperarPasswordForm,
    RegistroForm,
    ResetPasswordForm,
)

from .db import (
    col_albumes,
    col_artistas,
    col_playlists,
    col_reproducciones,
    col_tokens,
    col_usuarios,
)


# ---------------------------------------------------------------------------
# Helpers de sesión
# ---------------------------------------------------------------------------

def _login_requerido(request):
    return request.session.get('usuario_id') is None


def _artista_requerido(request):
    return not request.session.get('es_artista', False)


def _oid(value):
    """ObjectId seguro: retorna None si el string no es un ObjectId válido."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


# ---------------------------------------------------------------------------
# Helpers de traducción Mongo -> contexto de template (estilo SQL)
# ---------------------------------------------------------------------------

def _parse_duracion(valor):
    """'00:03:55' -> datetime.time(0, 3, 55) para el filtro |time:'i:s'."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%H:%M:%S').time()
    except (ValueError, TypeError):
        return None


def _duracion_a_segundos(valor):
    try:
        h, m, s = [int(x) for x in valor.split(':')]
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return 0


def _detectar_dispositivo(user_agent):
    """La colección 'reproducciones' en Atlas valida dispositivo contra un
    $jsonSchema con enum ['Movil', 'Web', 'Tablet']; no acepta el user-agent
    crudo."""
    ua = (user_agent or '').lower()
    if 'ipad' in ua or 'tablet' in ua:
        return 'Tablet'
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        return 'Movil'
    return 'Web'


def _parse_fecha(valor):
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor[:10], '%Y-%m-%d').date()
        except ValueError:
            return None
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def _persona_from_usuario_doc(u):
    perfil = u.get('perfil', {}) or {}
    return {
        'idpersona': str(u['_id']),
        'nombre': perfil.get('nombre', ''),
        'apellido': perfil.get('apellido', ''),
        'genero': perfil.get('genero', ''),
        'password': u.get('personaPassword', ''),
        'paisorigen': perfil.get('pais', ''),
        'fecharegistro': _parse_fecha(u.get('fechaRegistro')),
    }


_TIPO_SUSCRIPCION_LABELS = {
    'premium_individual': 'Premium Individual',
    'premium_familiar': 'Premium Familiar',
    'gratis': 'Gratuito',
}


def _usuario_ctx(u):
    sus = u.get('suscripcion') or {}
    tipo = sus.get('tipo')
    nombretipo = _TIPO_SUSCRIPCION_LABELS.get(tipo, tipo or 'Gratuito')
    return {
        'email': u.get('email', ''),
        'idtiposuscripcion': {'nombretipo': nombretipo} if sus.get('activa') else None,
    }


def _artista_ref_ctx(a):
    if not a:
        return None
    persona = a.get('persona', {}) or {}
    return {
        'idartista': str(a['_id']),
        'nombreartistico': a.get('nombreArtistico', ''),
        'oyentesmensuales': a.get('oyentesMensuales', 0),
        'idpersona': {
            'nombre': persona.get('nombre', ''),
            'apellido': persona.get('apellido', ''),
            'paisorigen': a.get('paisOrigen', ''),
        },
    }


def _album_ctx(a):
    return {
        'idalbum': str(a['_id']),
        'nombrealbum': a.get('nombreAlbum', ''),
        'fechalanzamiento': _parse_fecha(a.get('fechaLanzamiento')),
    }


def _cancion_ctx(album_doc, cancion_doc, artista_doc=None):
    album_id = str(album_doc['_id'])
    id_cancion = f"{album_id}:{cancion_doc.get('pista')}"
    return {
        'idcancion': id_cancion,
        'nombrecancion': cancion_doc.get('nombreCancion', ''),
        'duracion': _parse_duracion(cancion_doc.get('duracion')),
        'idalbum': {
            'idalbum': album_id,
            'nombrealbum': album_doc.get('nombreAlbum', ''),
            'idartista': _artista_ref_ctx(artista_doc) if artista_doc else None,
        },
        'idgenero': {'nombregenero': cancion_doc.get('genero') or album_doc.get('genero') or ''},
    }


def _playlist_ctx(pl):
    return {
        'idplaylist': str(pl['_id']),
        'nombreplaylist': pl.get('nombrePlaylist', ''),
        'descripcion': pl.get('descripcion', ''),
    }


def _get_album_and_cancion(id_cancion):
    """'<idAlbum>:<pista>' -> (album_doc, cancion_dict) o (None, None)."""
    if not id_cancion or ':' not in id_cancion:
        return None, None
    album_id_str, _, pista_str = id_cancion.partition(':')
    album_id = _oid(album_id_str)
    if not album_id:
        return None, None
    try:
        pista = int(pista_str)
    except ValueError:
        return None, None
    album = col_albumes().find_one({'_id': album_id})
    if not album:
        return None, None
    cancion = next((c for c in album.get('canciones', []) if c.get('pista') == pista), None)
    return album, cancion


def _artistas_por_nombre():
    return {a['nombreArtistico']: a for a in col_artistas().find()}


def _genero_choices_for_artista(artista_doc):
    generos = set(artista_doc.get('generos', []) or [])
    for alb in col_albumes().find({'artista': artista_doc.get('nombreArtistico')}):
        if alb.get('genero'):
            generos.add(alb['genero'])
        for c in alb.get('canciones', []):
            if c.get('genero'):
                generos.add(c['genero'])
    if not generos:
        generos = {'Pop', 'Rock', 'Reggaeton', 'Electronica', 'Balada'}
    return [SimpleNamespace(idgenero=g, nombregenero=g) for g in sorted(generos)]


def _album_choices_for_artista(artista_doc):
    return [
        SimpleNamespace(idalbum=str(a['_id']), nombrealbum=a.get('nombreAlbum', ''))
        for a in col_albumes().find({'artista': artista_doc.get('nombreArtistico')})
    ]


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def login_view(request):
    if request.session.get('usuario_id'):
        return redirect('mongo:index')

    if request.method == 'POST':
        credencial = request.POST.get('username', '').strip()
        password_ingresado = request.POST.get('password', '')

        # -- Acceso administrativo (demo, sin colección propia) --
        if credencial.lower() == 'admin':
            if password_ingresado == 'admin':
                request.session['usuario_id'] = 'admin'
                request.session['persona_id'] = 'admin'
                request.session['usuario_nombre'] = 'Administrador'
                request.session['email'] = ''
                request.session['es_artista'] = False
                request.session['es_admin'] = True
                messages.success(request, "¡Sesión iniciada como Admin!")
                return redirect('mongo:index')
            messages.error(request, "Contraseña incorrecta.")
            return render(request, 'streaming/login.html')

        # -- Artista (login por email o nombre artístico) --
        artista = col_artistas().find_one({
            '$or': [{'email': credencial}, {'nombreArtistico': credencial}]
        })
        if artista:
            pwd_hash = artista.get('passwordHash', '') or ''
            if pwd_hash.startswith('pbkdf2_') and check_password(password_ingresado, pwd_hash):
                persona = artista.get('persona', {}) or {}
                request.session['usuario_id'] = str(artista['_id'])
                request.session['persona_id'] = str(artista['_id'])
                request.session['usuario_nombre'] = f"{persona.get('nombre', '')} {persona.get('apellido', '')}".strip()
                request.session['email'] = artista.get('email', '')
                request.session['es_artista'] = True
                request.session['artista_id'] = str(artista['_id'])
                request.session['nombre_artistico'] = artista.get('nombreArtistico') or persona.get('nombre')
                request.session['es_admin'] = False
                messages.success(request, f"¡Bienvenido, {persona.get('nombre', '')}!")
                return redirect('mongo:index')
            messages.error(request, "Contraseña incorrecta.")
            return render(request, 'streaming/login.html')

        # -- Usuario oyente (login por email o nombre de usuario) --
        usuario = col_usuarios().find_one({
            '$or': [{'email': credencial}, {'nombreUsuario': credencial}]
        })
        if usuario:
            pwd_hash = usuario.get('passwordHash', '') or ''
            if pwd_hash.startswith('pbkdf2_') and check_password(password_ingresado, pwd_hash):
                perfil = usuario.get('perfil', {}) or {}
                request.session['usuario_id'] = str(usuario['_id'])
                request.session['persona_id'] = str(usuario['_id'])
                request.session['usuario_nombre'] = f"{perfil.get('nombre', '')} {perfil.get('apellido', '')}".strip()
                request.session['email'] = usuario.get('email', '')
                request.session['es_artista'] = False
                request.session['es_admin'] = False
                messages.success(request, f"¡Bienvenido, {perfil.get('nombre', '')}!")
                return redirect('mongo:index')
            messages.error(request, "Contraseña incorrecta.")
            return render(request, 'streaming/login.html')

        messages.error(request, "No existe una cuenta con ese correo o usuario.")

    return render(request, 'streaming/login.html')


def register_view(request):
    if request.session.get('usuario_id'):
        return redirect('mongo:index')

    form = RegistroForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        email = data['email']

        if col_usuarios().find_one({'email': email}) or col_artistas().find_one({'email': email}):
            messages.error(request, "Ya existe una cuenta con ese correo electrónico.")
            return render(request, 'streaming/register.html', {'form': form})

        hashed_pwd = make_password(data['password'])
        hoy = date.today().isoformat()
        fecha_nac = data.get('fecha_nacimiento').isoformat() if data.get('fecha_nacimiento') else None

        try:
            if data['tipo_cuenta'] == 'artista':
                col_artistas().insert_one({
                    'nombreArtistico': data.get('nombre_artistico'),
                    'email': email,
                    'passwordHash': hashed_pwd,
                    'persona': {
                        'nombre': data['nombre'],
                        'apellido': data['apellido'],
                        'fechaNacimiento': fecha_nac,
                        'genero': data.get('genero') or None,
                    },
                    'paisOrigen': data.get('pais_origen') or None,
                    'biografia': '',
                    'oyentesMensuales': 0,
                    'generos': [],
                    'redesSociales': {},
                    'verificado': False,
                    'fechaRegistro': hoy,
                })
            else:
                col_usuarios().insert_one({
                    'nombreUsuario': f"{data['nombre']}_{data['apellido']}".lower(),
                    'email': email,
                    'passwordHash': hashed_pwd,
                    'perfil': {
                        'nombre': data['nombre'],
                        'apellido': data['apellido'],
                        'fotoPerfil': None,
                        'pais': data.get('pais_origen') or None,
                        'fechaNacimiento': fecha_nac,
                        'genero': data.get('genero') or None,
                    },
                    'suscripcion': {
                        'tipo': 'gratis',
                        'precio': 0,
                        'fechaInicio': hoy,
                        'activa': True,
                    },
                    'preferencias': {
                        'generosFavoritos': [],
                        'idiomaApp': 'es',
                        'calidadAudio': 'media',
                        'descargarOffline': False,
                    },
                    'historialReciente': [],
                    'fechaRegistro': hoy,
                    'activo': True,
                })

            messages.success(request, "¡Cuenta creada exitosamente! Ya puedes iniciar sesión.")
            return redirect('mongo:login')

        except Exception as e:
            messages.error(request, f"Error al crear la cuenta: {e}")

    return render(request, 'streaming/register.html', {'form': form})


def logout_view(request):
    request.session.flush()
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect('mongo:login')


# ---------------------------------------------------------------------------
# Recuperación de contraseña (tokens guardados en Mongo, no en SQLite)
# ---------------------------------------------------------------------------

def recuperar_password_view(request):
    form = RecuperarPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        if col_usuarios().find_one({'email': email}) or col_artistas().find_one({'email': email}):
            col_tokens().update_many({'email': email, 'usado': False}, {'$set': {'usado': True}})
            token = str(uuid.uuid4())
            col_tokens().insert_one({
                'email': email,
                'token': token,
                'creado_en': timezone.now(),
                'usado': False,
            })
            reset_url = request.build_absolute_uri(f'/mongo/reset-password/{token}/')
            try:
                send_mail(
                    subject='SoundStream – Recupera tu contraseña',
                    message=(
                        f"Hola,\n\n"
                        f"Recibimos una solicitud para restablecer tu contraseña.\n"
                        f"Haz clic en el siguiente enlace (válido por 30 minutos):\n\n"
                        f"{reset_url}\n\n"
                        f"Si no solicitaste esto, ignora este mensaje.\n\n"
                        f"— Equipo SoundStream"
                    ),
                    from_email='noreply@soundstream.com',
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass

        messages.success(
            request,
            "Si ese correo existe en nuestro sistema, recibirás instrucciones en breve."
        )
        return redirect('mongo:login')

    return render(request, 'streaming/recuperar_password.html', {'form': form})


def reset_password_view(request, token):
    token_str = str(token)
    token_obj = col_tokens().find_one({'token': token_str, 'usado': False})
    if not token_obj:
        messages.error(request, "El enlace no es válido o ya fue utilizado.")
        return redirect('mongo:login')

    creado_en = token_obj['creado_en']
    if timezone.is_naive(creado_en):
        creado_en = timezone.make_aware(creado_en)
    if timezone.now() - creado_en > timedelta(minutes=30):
        col_tokens().update_one({'_id': token_obj['_id']}, {'$set': {'usado': True}})
        messages.error(request, "El enlace ha expirado. Solicita uno nuevo.")
        return redirect('mongo:recuperar_password')

    form = ResetPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        nueva_pwd = form.cleaned_data['password']
        email = token_obj['email']
        nuevo_hash = make_password(nueva_pwd)
        res = col_usuarios().update_one({'email': email}, {'$set': {'passwordHash': nuevo_hash}})
        if res.matched_count == 0:
            col_artistas().update_one({'email': email}, {'$set': {'passwordHash': nuevo_hash}})
        col_tokens().update_one({'_id': token_obj['_id']}, {'$set': {'usado': True}})
        messages.success(request, "Contraseña actualizada. Ya puedes iniciar sesión.")
        return redirect('mongo:login')

    return render(request, 'streaming/reset_password.html', {'form': form, 'token': token})


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

def index(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return render(request, 'streaming/index.html')

    es_admin = request.session.get('es_admin', False)
    es_artista = request.session.get('es_artista', False)

    if es_admin:
        personas = [_persona_from_usuario_doc(u) for u in col_usuarios().find()]
        return render(request, 'streaming/index.html', {
            'es_admin': True,
            'personas': personas,
        })

    if es_artista:
        return redirect('mongo:dashboard_artista')

    return redirect('mongo:dashboard_usuario')


# ---------------------------------------------------------------------------
# Dashboard Usuario
# ---------------------------------------------------------------------------

def dashboard_usuario_view(request):
    if _login_requerido(request):
        return redirect('mongo:login')
    if request.session.get('es_artista'):
        return redirect('mongo:dashboard_artista')

    usuario_id = request.session.get('usuario_id')
    usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)}) if _oid(usuario_id) else None
    if not usuario_doc:
        messages.error(request, "Sesión inválida.")
        request.session.flush()
        return redirect('mongo:login')

    playlists = [
        _playlist_ctx(pl)
        for pl in col_playlists().find({'creador': usuario_doc.get('nombreUsuario')})
    ]

    artistas_docs = list(col_artistas().find())
    artistas_by_nombre = {a['nombreArtistico']: a for a in artistas_docs}

    canciones = []
    for alb in col_albumes().find():
        artista_doc = artistas_by_nombre.get(alb.get('artista'))
        for c in sorted(alb.get('canciones', []), key=lambda x: x.get('pista', 0)):
            canciones.append(_cancion_ctx(alb, c, artista_doc))
            if len(canciones) >= 20:
                break
        if len(canciones) >= 20:
            break

    artistas = [_artista_ref_ctx(a) for a in artistas_docs]

    return render(request, 'streaming/dashboard_usuario.html', {
        'usuario': _usuario_ctx(usuario_doc),
        'persona': _persona_from_usuario_doc(usuario_doc),
        'playlists': playlists,
        'canciones': canciones,
        'artistas': artistas,
    })


# ---------------------------------------------------------------------------
# CRUD Playlists (Usuario)
# ---------------------------------------------------------------------------

def crear_playlist_view(request):
    if _login_requerido(request):
        return redirect('mongo:login')
    usuario_id = request.session.get('usuario_id')
    form = PlaylistForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)})
            col_playlists().insert_one({
                'nombrePlaylist': form.cleaned_data['nombre_playlist'],
                'descripcion': form.cleaned_data['descripcion'],
                'esPublica': False,
                'creador': usuario_doc.get('nombreUsuario') if usuario_doc else '',
                'canciones': [],
                'totalCanciones': 0,
                'duracionTotal': '00:00:00',
                'seguidores': 0,
                'fechaCreacion': timezone.now(),
                'ultimaModificacion': timezone.now(),
            })
            messages.success(request, "Playlist creada.")
            return redirect('mongo:dashboard_usuario')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/playlist_form.html', {'form': form, 'accion': 'Crear'})


def editar_playlist_view(request, pk):
    if _login_requerido(request):
        return redirect('mongo:login')
    usuario_id = request.session.get('usuario_id')
    usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)})
    playlist_id = _oid(pk)
    playlist = col_playlists().find_one({'_id': playlist_id, 'creador': usuario_doc.get('nombreUsuario')}) if playlist_id and usuario_doc else None

    if not playlist:
        messages.error(request, "Playlist no encontrada.")
        return redirect('mongo:dashboard_usuario')

    form = PlaylistForm(request.POST or None, initial={
        'nombre_playlist': playlist.get('nombrePlaylist', ''),
        'descripcion': playlist.get('descripcion', ''),
    })

    if request.method == 'POST' and form.is_valid():
        try:
            col_playlists().update_one(
                {'_id': playlist['_id']},
                {'$set': {
                    'nombrePlaylist': form.cleaned_data['nombre_playlist'],
                    'descripcion': form.cleaned_data['descripcion'],
                    'ultimaModificacion': timezone.now(),
                }}
            )
            messages.success(request, "Playlist actualizada.")
            return redirect('mongo:dashboard_usuario')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/playlist_form.html', {
        'form': form, 'accion': 'Editar', 'playlist': _playlist_ctx(playlist)
    })


def eliminar_playlist_view(request, pk):
    if _login_requerido(request):
        return redirect('mongo:login')
    usuario_id = request.session.get('usuario_id')
    usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)})
    if request.method == 'POST':
        try:
            playlist_id = _oid(pk)
            playlist = col_playlists().find_one({'_id': playlist_id, 'creador': usuario_doc.get('nombreUsuario')}) if playlist_id and usuario_doc else None
            if playlist:
                col_playlists().delete_one({'_id': playlist['_id']})
                messages.success(request, f"Playlist '{playlist.get('nombrePlaylist')}' eliminada.")
            else:
                messages.error(request, "Playlist no encontrada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('mongo:dashboard_usuario')


def playlist_detalle_view(request, pk):
    if _login_requerido(request):
        return redirect('mongo:login')
    usuario_id = request.session.get('usuario_id')
    usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)})
    playlist_id = _oid(pk)
    playlist = col_playlists().find_one({'_id': playlist_id, 'creador': usuario_doc.get('nombreUsuario')}) if playlist_id and usuario_doc else None

    if not playlist:
        messages.error(request, "Playlist no encontrada.")
        return redirect('mongo:dashboard_usuario')

    artistas_by_nombre = _artistas_por_nombre()

    canciones_en_playlist = []
    ids_en_playlist = set()
    for c in playlist.get('canciones', []):
        origen_id = c.get('origenId')
        resuelto = None
        if origen_id:
            album, cancion = _get_album_and_cancion(origen_id)
            if album and cancion:
                ids_en_playlist.add(origen_id)
                resuelto = _cancion_ctx(album, cancion, artistas_by_nombre.get(album.get('artista')))
        if not resuelto:
            resuelto = {
                'idcancion': origen_id or f"pl:{c.get('orden')}",
                'nombrecancion': c.get('nombreCancion', ''),
                'duracion': _parse_duracion(c.get('duracion')),
                'idalbum': {'nombrealbum': None, 'idartista': {'idpersona': {'nombre': c.get('artista', '')}}},
                'idgenero': {'nombregenero': ''},
            }
        canciones_en_playlist.append({'idcancion': resuelto})

    todas_canciones = []
    for alb in col_albumes().find():
        artista_doc = artistas_by_nombre.get(alb.get('artista'))
        for c in sorted(alb.get('canciones', []), key=lambda x: x.get('pista', 0)):
            id_cancion = f"{alb['_id']}:{c.get('pista')}"
            if id_cancion in ids_en_playlist:
                continue
            todas_canciones.append(_cancion_ctx(alb, c, artista_doc))

    return render(request, 'streaming/playlist_detalle.html', {
        'playlist': _playlist_ctx(playlist),
        'canciones_en_playlist': canciones_en_playlist,
        'todas_canciones': todas_canciones,
    })


def agregar_cancion_playlist_view(request, pk, id_cancion):
    if _login_requerido(request):
        return redirect('mongo:login')
    if request.method == 'POST':
        album, cancion = _get_album_and_cancion(id_cancion)
        playlist_id = _oid(pk)
        if not album or not cancion or not playlist_id:
            messages.error(request, "Canción no encontrada.")
            return redirect('mongo:playlist_detalle', pk=pk)
        try:
            playlist = col_playlists().find_one({'_id': playlist_id})
            canciones = playlist.get('canciones', [])
            if any(c.get('origenId') == id_cancion for c in canciones):
                messages.warning(request, "La canción ya está en esta playlist.")
            else:
                canciones.append({
                    'nombreCancion': cancion.get('nombreCancion'),
                    'artista': album.get('artista'),
                    'duracion': cancion.get('duracion'),
                    'fechaAgregada': timezone.now(),
                    'orden': len(canciones) + 1,
                    'origenId': id_cancion,
                })
                col_playlists().update_one(
                    {'_id': playlist['_id']},
                    {'$set': {
                        'canciones': canciones,
                        'totalCanciones': len(canciones),
                        'ultimaModificacion': timezone.now(),
                    }}
                )
                messages.success(request, "Canción agregada a la playlist.")
        except Exception:
            messages.warning(request, "La canción ya está en esta playlist.")
    return redirect('mongo:playlist_detalle', pk=pk)


def quitar_cancion_playlist_view(request, pk, id_cancion):
    if _login_requerido(request):
        return redirect('mongo:login')
    if request.method == 'POST':
        try:
            playlist_id = _oid(pk)
            playlist = col_playlists().find_one({'_id': playlist_id}) if playlist_id else None
            if playlist:
                nuevas = [c for c in playlist.get('canciones', []) if c.get('origenId') != id_cancion]
                col_playlists().update_one(
                    {'_id': playlist['_id']},
                    {'$set': {
                        'canciones': nuevas,
                        'totalCanciones': len(nuevas),
                        'ultimaModificacion': timezone.now(),
                    }}
                )
                messages.success(request, "Canción eliminada de la playlist.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('mongo:playlist_detalle', pk=pk)


# ---------------------------------------------------------------------------
# Dashboard Artista
# ---------------------------------------------------------------------------

def dashboard_artista_view(request):
    if _login_requerido(request):
        return redirect('mongo:login')
    if not request.session.get('es_artista'):
        return redirect('mongo:dashboard_usuario')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    if not artista_doc:
        messages.error(request, "Perfil de artista no encontrado.")
        request.session.flush()
        return redirect('mongo:login')

    albums_docs = list(col_albumes().find({'artista': artista_doc.get('nombreArtistico')}))
    albums_docs.sort(key=lambda a: a.get('fechaLanzamiento') or '', reverse=True)
    albums = [_album_ctx(a) for a in albums_docs]
    total_canciones = sum(len(a.get('canciones', [])) for a in albums_docs)

    return render(request, 'streaming/dashboard_artista.html', {
        'artista': _artista_ref_ctx(artista_doc),
        'albums': albums,
        'total_canciones': total_canciones,
    })


def artista_editar_perfil_view(request):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    if not artista_doc:
        messages.error(request, "Artista no encontrado.")
        return redirect('mongo:login')

    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombre_artistico', '').strip()
        oyentes = request.POST.get('oyentes_mensuales', '').strip()
        try:
            col_artistas().update_one(
                {'_id': artista_doc['_id']},
                {'$set': {
                    'nombreArtistico': nombre_artistico or artista_doc.get('nombreArtistico'),
                    'oyentesMensuales': int(oyentes or 0),
                }}
            )
            request.session['nombre_artistico'] = nombre_artistico or artista_doc.get('nombreArtistico')
            messages.success(request, "Perfil artístico actualizado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('mongo:dashboard_artista')

    return render(request, 'streaming/artista_perfil_form.html', {'artista': _artista_ref_ctx(artista_doc)})


# ---------------------------------------------------------------------------
# CRUD Álbumes (Artista)
# ---------------------------------------------------------------------------

def crear_album_view(request):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    form = AlbumForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            col_albumes().insert_one({
                'nombreAlbum': form.cleaned_data['nombre_album'],
                'fechaLanzamiento': form.cleaned_data['fecha_lanzamiento'].isoformat(),
                'portada': None,
                'artista': artista_doc.get('nombreArtistico') if artista_doc else '',
                'genero': (artista_doc.get('generos') or [''])[0] if artista_doc else '',
                'totalCanciones': 0,
                'duracionTotal': '00:00:00',
                'canciones': [],
            })
            messages.success(request, "Álbum creado exitosamente.")
            return redirect('mongo:dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/album_form.html', {'form': form, 'accion': 'Crear'})


def editar_album_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    album_id = _oid(pk)
    album = col_albumes().find_one({'_id': album_id, 'artista': artista_doc.get('nombreArtistico')}) if album_id and artista_doc else None

    if not album:
        messages.error(request, "Álbum no encontrado.")
        return redirect('mongo:dashboard_artista')

    fecha_actual = album.get('fechaLanzamiento')
    fecha_initial = fecha_actual[:10] if isinstance(fecha_actual, str) else fecha_actual

    form = AlbumForm(request.POST or None, initial={
        'nombre_album': album.get('nombreAlbum', ''),
        'fecha_lanzamiento': fecha_initial,
    })

    if request.method == 'POST' and form.is_valid():
        try:
            col_albumes().update_one(
                {'_id': album['_id']},
                {'$set': {
                    'nombreAlbum': form.cleaned_data['nombre_album'],
                    'fechaLanzamiento': form.cleaned_data['fecha_lanzamiento'].isoformat(),
                }}
            )
            messages.success(request, "Álbum actualizado.")
            return redirect('mongo:dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/album_form.html', {
        'form': form, 'accion': 'Editar', 'album': _album_ctx(album)
    })


def eliminar_album_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    if request.method == 'POST':
        try:
            album_id = _oid(pk)
            album = col_albumes().find_one({'_id': album_id, 'artista': artista_doc.get('nombreArtistico')}) if album_id and artista_doc else None
            if album:
                id_album_str = str(album['_id'])
                col_albumes().delete_one({'_id': album['_id']})
                for pl in col_playlists().find({'canciones.origenId': {'$regex': f'^{id_album_str}:'}}):
                    nuevas = [
                        c for c in pl.get('canciones', [])
                        if not str(c.get('origenId', '')).startswith(f'{id_album_str}:')
                    ]
                    col_playlists().update_one(
                        {'_id': pl['_id']},
                        {'$set': {'canciones': nuevas, 'totalCanciones': len(nuevas)}}
                    )
                messages.success(request, "Álbum y sus canciones eliminados.")
            else:
                messages.error(request, "Álbum no encontrado.")
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")
    return redirect('mongo:dashboard_artista')


# ---------------------------------------------------------------------------
# CRUD Canciones (Artista)
# ---------------------------------------------------------------------------

def album_canciones_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    album_id = _oid(pk)
    album = col_albumes().find_one({'_id': album_id, 'artista': artista_doc.get('nombreArtistico')}) if album_id and artista_doc else None

    if not album:
        messages.error(request, "Álbum no encontrado.")
        return redirect('mongo:dashboard_artista')

    canciones = [
        _cancion_ctx(album, c, artista_doc)
        for c in sorted(album.get('canciones', []), key=lambda x: x.get('pista', 0))
    ]

    return render(request, 'streaming/album_canciones.html', {
        'album': _album_ctx(album),
        'canciones': canciones,
    })


def crear_cancion_view(request, id_album):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    album_id = _oid(id_album)
    album = col_albumes().find_one({'_id': album_id, 'artista': artista_doc.get('nombreArtistico')}) if album_id and artista_doc else None

    if not album:
        messages.error(request, "Álbum no encontrado.")
        return redirect('mongo:dashboard_artista')

    generos = _genero_choices_for_artista(artista_doc)
    albums = _album_choices_for_artista(artista_doc)
    form = CancionForm(request.POST or None, generos=generos, albums=albums)

    if request.method == 'POST' and form.is_valid():
        try:
            destino_id = form.cleaned_data['id_album']
            destino = album if destino_id == str(album['_id']) else col_albumes().find_one({'_id': _oid(destino_id)})
            duracion_str = form.cleaned_data['duracion']
            siguiente_pista = max([c.get('pista', 0) for c in destino.get('canciones', [])], default=0) + 1
            nueva = {
                'pista': siguiente_pista,
                'nombreCancion': form.cleaned_data['nombre_cancion'],
                'duracion': duracion_str,
                'duracionSegundos': _duracion_a_segundos(duracion_str),
                'genero': form.cleaned_data['id_genero'],
                'letra': False,
                'explicit': False,
                'reproducciones': 0,
            }
            canciones = destino.get('canciones', []) + [nueva]
            col_albumes().update_one(
                {'_id': destino['_id']},
                {'$set': {'canciones': canciones, 'totalCanciones': len(canciones)}}
            )
            messages.success(request, "Canción agregada.")
            return redirect('mongo:album_canciones', pk=id_album)
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/cancion_form.html', {
        'form': form, 'accion': 'Crear', 'album': _album_ctx(album)
    })


def editar_cancion_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    artista_id = request.session.get('artista_id')
    artista_doc = col_artistas().find_one({'_id': _oid(artista_id)}) if _oid(artista_id) else None
    album, cancion = _get_album_and_cancion(pk)
    if not album or not cancion or not artista_doc or album.get('artista') != artista_doc.get('nombreArtistico'):
        messages.error(request, "Canción no encontrada.")
        return redirect('mongo:dashboard_artista')

    generos = _genero_choices_for_artista(artista_doc)
    albums = _album_choices_for_artista(artista_doc)

    form = CancionForm(
        request.POST or None,
        generos=generos, albums=albums,
        initial={
            'nombre_cancion': cancion.get('nombreCancion', ''),
            'duracion': cancion.get('duracion', ''),
            'id_genero': cancion.get('genero', ''),
            'id_album': str(album['_id']),
        }
    )

    if request.method == 'POST' and form.is_valid():
        try:
            destino_id = form.cleaned_data['id_album']
            duracion_str = form.cleaned_data['duracion']

            if destino_id != str(album['_id']):
                # Mover la canción a otro álbum del mismo artista.
                canciones_origen = [c for c in album.get('canciones', []) if c.get('pista') != cancion.get('pista')]
                col_albumes().update_one(
                    {'_id': album['_id']},
                    {'$set': {'canciones': canciones_origen, 'totalCanciones': len(canciones_origen)}}
                )

                destino = col_albumes().find_one({'_id': _oid(destino_id)})
                siguiente_pista = max([c.get('pista', 0) for c in destino.get('canciones', [])], default=0) + 1
                nueva = {
                    'pista': siguiente_pista,
                    'nombreCancion': form.cleaned_data['nombre_cancion'],
                    'duracion': duracion_str,
                    'duracionSegundos': _duracion_a_segundos(duracion_str),
                    'genero': form.cleaned_data['id_genero'],
                    'letra': cancion.get('letra', False),
                    'explicit': cancion.get('explicit', False),
                    'reproducciones': cancion.get('reproducciones', 0),
                }
                canciones_destino = destino.get('canciones', []) + [nueva]
                col_albumes().update_one(
                    {'_id': destino['_id']},
                    {'$set': {'canciones': canciones_destino, 'totalCanciones': len(canciones_destino)}}
                )
                messages.success(request, "Canción actualizada y movida de álbum.")
                return redirect('mongo:album_canciones', pk=destino_id)

            canciones = album.get('canciones', [])
            for c in canciones:
                if c.get('pista') == cancion.get('pista'):
                    c['nombreCancion'] = form.cleaned_data['nombre_cancion']
                    c['duracion'] = duracion_str
                    c['duracionSegundos'] = _duracion_a_segundos(duracion_str)
                    c['genero'] = form.cleaned_data['id_genero']
                    break
            col_albumes().update_one({'_id': album['_id']}, {'$set': {'canciones': canciones}})
            messages.success(request, "Canción actualizada.")
            return redirect('mongo:album_canciones', pk=str(album['_id']))
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/cancion_form.html', {
        'form': form, 'accion': 'Editar',
        'cancion': _cancion_ctx(album, cancion, artista_doc),
        'album': _album_ctx(album),
    })


def eliminar_cancion_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('mongo:login')

    album, cancion = _get_album_and_cancion(pk)
    if not album or not cancion:
        messages.error(request, "Canción no encontrada.")
        return redirect('mongo:dashboard_artista')

    id_album = str(album['_id'])
    if request.method == 'POST':
        try:
            canciones = [c for c in album.get('canciones', []) if c.get('pista') != cancion.get('pista')]
            col_albumes().update_one(
                {'_id': album['_id']},
                {'$set': {'canciones': canciones, 'totalCanciones': len(canciones)}}
            )
            for pl in col_playlists().find({'canciones.origenId': pk}):
                nuevas = [c for c in pl.get('canciones', []) if c.get('origenId') != pk]
                col_playlists().update_one(
                    {'_id': pl['_id']},
                    {'$set': {'canciones': nuevas, 'totalCanciones': len(nuevas)}}
                )
            messages.success(request, "Canción eliminada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('mongo:album_canciones', pk=id_album)


# ---------------------------------------------------------------------------
# Reproducción
# ---------------------------------------------------------------------------

def registrar_escucha_view(request, id_cancion):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('mongo:login')

    dispositivo = _detectar_dispositivo(request.META.get('HTTP_USER_AGENT', ''))

    if request.method == 'POST':
        album, cancion = _get_album_and_cancion(id_cancion)
        if album and cancion:
            usuario_doc = col_usuarios().find_one({'_id': _oid(usuario_id)}) if _oid(usuario_id) else None
            col_reproducciones().insert_one({
                'usuario': usuario_doc.get('nombreUsuario') if usuario_doc else request.session.get('usuario_nombre', ''),
                'nombreCancion': cancion.get('nombreCancion'),
                'artista': album.get('artista'),
                'dispositivo': dispositivo,
                'duracionEscuchada': cancion.get('duracionSegundos', 0),
                'completada': True,
                'fechaHora': timezone.now(),
            })
            col_albumes().update_one(
                {'_id': album['_id'], 'canciones.pista': cancion.get('pista')},
                {'$inc': {'canciones.$.reproducciones': 1}}
            )
            messages.success(request, "¡Escucha registrada!")
        else:
            messages.error(request, "Canción no encontrada.")
    return redirect(request.META.get('HTTP_REFERER', '/mongo/'))


# ---------------------------------------------------------------------------
# CRUD Admin (Persona <- colección usuarios)
# ---------------------------------------------------------------------------

def crear_persona_view(request):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('mongo:index')
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '')
            apellido = request.POST.get('apellido', '')
            password = request.POST.get('password', '')
            col_usuarios().insert_one({
                'nombreUsuario': f"{nombre}_{apellido}".lower(),
                'email': f"{nombre}.{apellido}@email.com".lower(),
                'passwordHash': make_password(password or '123456'),
                'personaPassword': password,
                'perfil': {
                    'nombre': nombre,
                    'apellido': apellido,
                    'fotoPerfil': None,
                    'pais': request.POST.get('paisorigen', ''),
                    'fechaNacimiento': None,
                    'genero': request.POST.get('genero', ''),
                },
                'suscripcion': {
                    'tipo': 'gratis', 'precio': 0,
                    'fechaInicio': request.POST.get('fecharegistro') or date.today().isoformat(),
                    'activa': True,
                },
                'preferencias': {
                    'generosFavoritos': [], 'idiomaApp': 'es',
                    'calidadAudio': 'media', 'descargarOffline': False,
                },
                'historialReciente': [],
                'fechaRegistro': request.POST.get('fecharegistro') or date.today().isoformat(),
                'activo': True,
            })
            messages.success(request, "Persona registrada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('mongo:index')
    return render(request, 'streaming/form_persona.html', {'accion': 'Crear'})


def editar_persona_view(request, pk):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('mongo:index')
    usuario_id = _oid(pk)
    usuario_doc = col_usuarios().find_one({'_id': usuario_id}) if usuario_id else None
    if not usuario_doc:
        messages.error(request, "Registro no encontrado.")
        return redirect('mongo:index')

    if request.method == 'POST':
        try:
            col_usuarios().update_one(
                {'_id': usuario_doc['_id']},
                {'$set': {
                    'perfil.nombre': request.POST.get('nombre', ''),
                    'perfil.apellido': request.POST.get('apellido', ''),
                    'perfil.genero': request.POST.get('genero', ''),
                    'perfil.pais': request.POST.get('paisorigen', ''),
                    'personaPassword': request.POST.get('password', usuario_doc.get('personaPassword', '')),
                }}
            )
            messages.success(request, "Registro actualizado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('mongo:index')
    return render(request, 'streaming/form_persona.html', {
        'persona': _persona_from_usuario_doc(usuario_doc), 'accion': 'Editar'
    })


def eliminar_persona_view(request, pk):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('mongo:index')
    if request.method == 'POST':
        usuario_id = _oid(pk)
        if usuario_id:
            col_usuarios().delete_one({'_id': usuario_id})
            messages.success(request, "Registro eliminado.")
        else:
            messages.error(request, "ID inválido.")
    return redirect('mongo:index')


def reporte_artista_view(request):
    artistas_docs = list(col_artistas().find())
    artistas = [{'idartista': str(a['_id']), 'nombreartistico': a.get('nombreArtistico', '')} for a in artistas_docs]

    artista_seleccionado = request.GET.get('artista_id') or None
    nombre_artista = None
    reporte_datos = []

    if artista_seleccionado:
        artista_oid = _oid(artista_seleccionado)
        artista_doc = col_artistas().find_one({'_id': artista_oid}) if artista_oid else None
        if artista_doc:
            nombre_artista = artista_doc.get('nombreArtistico', '')
            for alb in col_albumes().find({'artista': nombre_artista}):
                for c in sorted(alb.get('canciones', []), key=lambda x: x.get('pista', 0)):
                    reporte_datos.append({
                        'nombreArtistico': nombre_artista,
                        'nombreAlbum': alb.get('nombreAlbum', ''),
                        'nombreCancion': c.get('nombreCancion', ''),
                        'duracion': c.get('duracion', ''),
                    })

    return render(request, 'streaming/reporte_artista.html', {
        'artistas': artistas,
        'artista_seleccionado': artista_seleccionado,
        'nombre_artista': nombre_artista,
        'reporte_datos': reporte_datos,
    })
