# streaming/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.utils import timezone
from datetime import date, timedelta
import uuid

from .models import (
    Persona, Reproduccion, Pagosuscripcion, Usuario, Artista,
    Perfil, Album, Cancion, Genero, Playlist, PlaylistCancion,
    TipoSuscripcion, TokenRecuperacion,
)
from .forms import (
    RegistroForm, RecuperarPasswordForm, ResetPasswordForm,
    AlbumForm, CancionForm, PlaylistForm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_next_persona_id():
    with connection.cursor() as cursor:
        cursor.execute("SELECT ISNULL(MAX(idPersona), 0) + 1 FROM dbo.Persona")
        return cursor.fetchone()[0]


def _login_requerido(request):
    return request.session.get('usuario_id') is None


def _artista_requerido(request):
    return not request.session.get('es_artista', False)


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def login_view(request):
    if request.session.get('usuario_id'):
        return redirect('index')

    if request.method == 'POST':
        credencial = request.POST.get('username', '').strip()
        password_ingresado = request.POST.get('password', '')

        # -- Flujo nuevo: login por email (UsuariosBase.Usuario) --
        if '@' in credencial:
            try:
                usuario = Usuario.objects.select_related('idpersona').get(email=credencial)
                pwd_almacenado = usuario.password or ''
                es_valido = (
                    check_password(password_ingresado, pwd_almacenado)
                    if pwd_almacenado.startswith('pbkdf2_')
                    else pwd_almacenado == password_ingresado
                )
                if es_valido:
                    persona = usuario.idpersona
                    request.session['usuario_id'] = usuario.idusuario
                    request.session['persona_id'] = persona.idpersona
                    request.session['usuario_nombre'] = f"{persona.nombre} {persona.apellido}"
                    request.session['email'] = usuario.email

                    try:
                        artista = Artista.objects.get(idpersona=persona)
                        request.session['es_artista'] = True
                        request.session['artista_id'] = artista.idartista
                        request.session['nombre_artistico'] = artista.nombreartistico or persona.nombre
                    except Artista.DoesNotExist:
                        request.session['es_artista'] = False

                    request.session['es_admin'] = False
                    messages.success(request, f"¡Bienvenido, {persona.nombre}!")
                    return redirect('index')
                else:
                    messages.error(request, "Contraseña incorrecta.")
            except Usuario.DoesNotExist:
                messages.error(request, "No existe una cuenta con ese correo.")

        # -- Flujo legado: login por nombre (admin / datos de prueba) --
        else:
            try:
                persona = Persona.objects.get(nombre=credencial)
                if persona.password == password_ingresado:
                    request.session['usuario_id'] = persona.idpersona
                    request.session['persona_id'] = persona.idpersona
                    request.session['usuario_nombre'] = f"{persona.nombre} {persona.apellido}"
                    request.session['es_admin'] = persona.nombre.lower() == 'admin'
                    
                    try:
                        artista = Artista.objects.get(idpersona=persona)
                        request.session['es_artista'] = True
                        request.session['artista_id'] = artista.idartista
                        request.session['nombre_artistico'] = artista.nombreartistico or persona.nombre
                    except Artista.DoesNotExist:
                        request.session['es_artista'] = False
                        
                    messages.success(request, f"¡Sesión iniciada como {persona.nombre}!")
                    return redirect('index')
                else:
                    messages.error(request, "Contraseña incorrecta.")
            except Persona.DoesNotExist:
                messages.error(request, "El usuario no se encuentra registrado.")

    return render(request, 'streaming/login.html')


def register_view(request):
    if request.session.get('usuario_id'):
        return redirect('index')

    form = RegistroForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        email = data['email']

        # Verificar email único
        if Usuario.objects.filter(email=email).exists():
            messages.error(request, "Ya existe una cuenta con ese correo electrónico.")
            return render(request, 'streaming/register.html', {'form': form})

        try:
            next_id = _get_next_persona_id()
            hoy = date.today()
            hashed_pwd = make_password(data['password'])

            # Insertar Persona (sin IDENTITY, sin ORM para evitar problemas de managed=False)
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO dbo.Persona
                       (idPersona, nombre, apellido, fechaRegistro, genero,
                        password, verificado, paisOrigen, fechaNacimiento)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        next_id,
                        data['nombre'],
                        data['apellido'],
                        hoy,
                        data.get('genero') or None,
                        'hashed',  # placeholder; contraseña real va en Usuario
                        'Si',
                        data.get('pais_origen') or None,
                        data.get('fecha_nacimiento') or None,
                    ]
                )

                # Insertar Usuario (IDENTITY en idUsuario)
                cursor.execute(
                    """INSERT INTO UsuariosBase.Usuario
                       (idPersona, email, password, fechaRegistro, idTipoSuscripcion)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [next_id, email, hashed_pwd, hoy, 1]
                )

                if data['tipo_cuenta'] == 'artista':
                    cursor.execute(
                        """INSERT INTO Artistas.Artista (idPersona, nombreArtistico, oyentesMensuales)
                           VALUES (%s, %s, %s)""",
                        [next_id, data.get('nombre_artistico'), 0]
                    )
                else:
                    # Obtener idUsuario recién creado
                    cursor.execute(
                        "SELECT idUsuario FROM UsuariosBase.Usuario WHERE idPersona = %s",
                        [next_id]
                    )
                    row = cursor.fetchone()
                    if row:
                        id_usuario = row[0]
                        cursor.execute(
                            """INSERT INTO Perfiles.Perfil
                               (idUsuario, nombreUsuario, fotoPerfil, pais, fechaNacimiento)
                               VALUES (%s, %s, %s, %s, %s)""",
                            [
                                id_usuario,
                                f"{data['nombre']}_{data['apellido']}".lower(),
                                None,
                                data.get('pais_origen') or None,
                                data.get('fecha_nacimiento') or None,
                            ]
                        )

            messages.success(request, "¡Cuenta creada exitosamente! Ya puedes iniciar sesión.")
            return redirect('login')

        except Exception as e:
            messages.error(request, f"Error al crear la cuenta: {e}")

    return render(request, 'streaming/register.html', {'form': form})


def logout_view(request):
    request.session.flush()
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect('login')


# ---------------------------------------------------------------------------
# Recuperación de contraseña
# ---------------------------------------------------------------------------

def recuperar_password_view(request):
    form = RecuperarPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        if Usuario.objects.filter(email=email).exists():
            # Invalidar tokens anteriores del mismo email
            TokenRecuperacion.objects.filter(email=email, usado=False).update(usado=True)

            token = TokenRecuperacion.objects.create(email=email)
            reset_url = request.build_absolute_uri(f'/reset-password/{token.token}/')

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
                fail_silently=False,
            )

        # Siempre mostramos el mismo mensaje por seguridad
        messages.success(
            request,
            "Si ese correo existe en nuestro sistema, recibirás instrucciones en breve."
        )
        return redirect('login')

    return render(request, 'streaming/recuperar_password.html', {'form': form})


def reset_password_view(request, token):
    try:
        token_obj = TokenRecuperacion.objects.get(token=token, usado=False)
    except TokenRecuperacion.DoesNotExist:
        messages.error(request, "El enlace no es válido o ya fue utilizado.")
        return redirect('login')

    # Expirar tokens de más de 30 minutos
    if timezone.now() - token_obj.creado_en > timedelta(minutes=30):
        token_obj.usado = True
        token_obj.save()
        messages.error(request, "El enlace ha expirado. Solicita uno nuevo.")
        return redirect('recuperar_password')

    form = ResetPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        nueva_pwd = form.cleaned_data['password']
        try:
            usuario = Usuario.objects.get(email=token_obj.email)
            usuario.password = make_password(nueva_pwd)
            usuario.save()
            token_obj.usado = True
            token_obj.save()
            messages.success(request, "Contraseña actualizada. Ya puedes iniciar sesión.")
            return redirect('login')
        except Usuario.DoesNotExist:
            messages.error(request, "No se encontró la cuenta asociada.")
            return redirect('login')

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
        return render(request, 'streaming/index.html', {
            'es_admin': True,
            'personas': Persona.objects.all(),
        })

    if es_artista:
        return redirect('dashboard_artista')

    return redirect('dashboard_usuario')


# ---------------------------------------------------------------------------
# Dashboard Usuario
# ---------------------------------------------------------------------------

def dashboard_usuario_view(request):
    if _login_requerido(request):
        return redirect('login')
    if request.session.get('es_artista'):
        return redirect('dashboard_artista')

    usuario_id = request.session.get('usuario_id')

    try:
        usuario = Usuario.objects.select_related('idpersona', 'idtiposuscripcion').get(idusuario=usuario_id)
    except Usuario.DoesNotExist:
        messages.error(request, "Sesión inválida.")
        request.session.flush()
        return redirect('login')

    playlists = Playlist.objects.filter(idusuario=usuario_id)
    canciones = Cancion.objects.select_related('idalbum__idartista__idpersona', 'idgenero').all()[:20]
    artistas = Artista.objects.select_related('idpersona').all()

    return render(request, 'streaming/dashboard_usuario.html', {
        'usuario': usuario,
        'persona': usuario.idpersona,
        'playlists': playlists,
        'canciones': canciones,
        'artistas': artistas,
    })


# ---------------------------------------------------------------------------
# CRUD Playlists (Usuario)
# ---------------------------------------------------------------------------

def crear_playlist_view(request):
    if _login_requerido(request):
        return redirect('login')
    usuario_id = request.session.get('usuario_id')
    form = PlaylistForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO Playlists.Playlist (nombrePlaylist, descripcion, idUsuario) VALUES (%s, %s, %s)",
                    [form.cleaned_data['nombre_playlist'], form.cleaned_data['descripcion'], usuario_id]
                )
            messages.success(request, "Playlist creada.")
            return redirect('dashboard_usuario')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/playlist_form.html', {'form': form, 'accion': 'Crear'})


def editar_playlist_view(request, pk):
    if _login_requerido(request):
        return redirect('login')
    usuario_id = request.session.get('usuario_id')

    try:
        playlist = Playlist.objects.get(idplaylist=pk, idusuario=usuario_id)
    except Playlist.DoesNotExist:
        messages.error(request, "Playlist no encontrada.")
        return redirect('dashboard_usuario')

    form = PlaylistForm(request.POST or None, initial={
        'nombre_playlist': playlist.nombreplaylist,
        'descripcion': playlist.descripcion,
    })

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE Playlists.Playlist SET nombrePlaylist = %s, descripcion = %s WHERE idPlaylist = %s",
                    [form.cleaned_data['nombre_playlist'], form.cleaned_data['descripcion'], pk]
                )
            messages.success(request, "Playlist actualizada.")
            return redirect('dashboard_usuario')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/playlist_form.html', {
        'form': form, 'accion': 'Editar', 'playlist': playlist
    })


def eliminar_playlist_view(request, pk):
    if _login_requerido(request):
        return redirect('login')
    usuario_id = request.session.get('usuario_id')
    if request.method == 'POST':
        try:
            playlist = Playlist.objects.get(idplaylist=pk, idusuario=usuario_id)
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM Playlists.PlaylistCancion WHERE idPlaylist = %s", [pk]
                )
                cursor.execute(
                    "DELETE FROM Playlists.Playlist WHERE idPlaylist = %s AND idUsuario = %s",
                    [pk, usuario_id]
                )
            messages.success(request, f"Playlist '{playlist.nombreplaylist}' eliminada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard_usuario')


def playlist_detalle_view(request, pk):
    if _login_requerido(request):
        return redirect('login')
    usuario_id = request.session.get('usuario_id')

    try:
        playlist = Playlist.objects.get(idplaylist=pk, idusuario=usuario_id)
    except Playlist.DoesNotExist:
        messages.error(request, "Playlist no encontrada.")
        return redirect('dashboard_usuario')

    canciones_en_playlist = PlaylistCancion.objects.filter(
        idplaylist=pk
    ).select_related('idcancion__idalbum__idartista__idpersona', 'idcancion__idgenero')

    ids_en_playlist = {pc.idcancion.idcancion for pc in canciones_en_playlist}
    todas_canciones = Cancion.objects.select_related(
        'idalbum__idartista__idpersona', 'idgenero'
    ).exclude(idcancion__in=ids_en_playlist)

    return render(request, 'streaming/playlist_detalle.html', {
        'playlist': playlist,
        'canciones_en_playlist': canciones_en_playlist,
        'todas_canciones': todas_canciones,
    })


def agregar_cancion_playlist_view(request, pk, id_cancion):
    if _login_requerido(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO Playlists.PlaylistCancion (idPlaylist, idCancion, fechaAgregada)
                       VALUES (%s, %s, %s)""",
                    [pk, id_cancion, date.today()]
                )
            messages.success(request, "Canción agregada a la playlist.")
        except Exception:
            messages.warning(request, "La canción ya está en esta playlist.")
    return redirect('playlist_detalle', pk=pk)


def quitar_cancion_playlist_view(request, pk, id_cancion):
    if _login_requerido(request):
        return redirect('login')
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM Playlists.PlaylistCancion WHERE idPlaylist = %s AND idCancion = %s",
                    [pk, id_cancion]
                )
            messages.success(request, "Canción eliminada de la playlist.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('playlist_detalle', pk=pk)


# ---------------------------------------------------------------------------
# Dashboard Artista
# ---------------------------------------------------------------------------

def dashboard_artista_view(request):
    if _login_requerido(request):
        return redirect('login')
    if not request.session.get('es_artista'):
        return redirect('dashboard_usuario')

    artista_id = request.session.get('artista_id')

    try:
        artista = Artista.objects.select_related('idpersona').get(idartista=artista_id)
    except Artista.DoesNotExist:
        messages.error(request, "Perfil de artista no encontrado.")
        request.session.flush()
        return redirect('login')

    albums = Album.objects.filter(idartista=artista_id).order_by('-fechalanzamiento')
    total_canciones = Cancion.objects.filter(idalbum__idartista=artista_id).count()

    return render(request, 'streaming/dashboard_artista.html', {
        'artista': artista,
        'albums': albums,
        'total_canciones': total_canciones,
    })


def artista_editar_perfil_view(request):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    artista = get_object_or_404(Artista, idartista=artista_id)

    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombre_artistico', '').strip()
        oyentes = request.POST.get('oyentes_mensuales', '').strip()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE Artistas.Artista
                       SET nombreArtistico = %s, oyentesMensuales = %s
                       WHERE idArtista = %s""",
                    [nombre_artistico or artista.nombreartistico, int(oyentes or 0), artista_id]
                )
            request.session['nombre_artistico'] = nombre_artistico or artista.nombreartistico
            messages.success(request, "Perfil artístico actualizado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('dashboard_artista')

    return render(request, 'streaming/artista_perfil_form.html', {'artista': artista})


# ---------------------------------------------------------------------------
# CRUD Álbumes (Artista)
# ---------------------------------------------------------------------------

def crear_album_view(request):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    form = AlbumForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO Albumes.Album (nombreAlbum, fechaLanzamiento, idArtista)
                       VALUES (%s, %s, %s)""",
                    [form.cleaned_data['nombre_album'], form.cleaned_data['fecha_lanzamiento'], artista_id]
                )
            messages.success(request, "Álbum creado exitosamente.")
            return redirect('dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/album_form.html', {'form': form, 'accion': 'Crear'})


def editar_album_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    album = get_object_or_404(Album, idalbum=pk, idartista=artista_id)

    form = AlbumForm(request.POST or None, initial={
        'nombre_album': album.nombrealbum,
        'fecha_lanzamiento': album.fechalanzamiento,
    })

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE Albumes.Album
                       SET nombreAlbum = %s, fechaLanzamiento = %s
                       WHERE idAlbum = %s AND idArtista = %s""",
                    [form.cleaned_data['nombre_album'], form.cleaned_data['fecha_lanzamiento'], pk, artista_id]
                )
            messages.success(request, "Álbum actualizado.")
            return redirect('dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/album_form.html', {'form': form, 'accion': 'Editar', 'album': album})


def eliminar_album_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                # Eliminar likes y reproducciones de canciones del álbum primero
                cursor.execute(
                    """DELETE FROM dbo.likeCancion WHERE idCancion IN
                       (SELECT idCancion FROM CancionesLogica.Cancion WHERE idAlbum = %s)""", [pk]
                )
                cursor.execute(
                    """DELETE FROM Playlists.PlaylistCancion WHERE idCancion IN
                       (SELECT idCancion FROM CancionesLogica.Cancion WHERE idAlbum = %s)""", [pk]
                )
                cursor.execute(
                    "DELETE FROM CancionesLogica.Cancion WHERE idAlbum = %s", [pk]
                )
                cursor.execute(
                    "DELETE FROM Albumes.Album WHERE idAlbum = %s AND idArtista = %s",
                    [pk, artista_id]
                )
            messages.success(request, "Álbum y sus canciones eliminados.")
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")
    return redirect('dashboard_artista')


# ---------------------------------------------------------------------------
# CRUD Canciones (Artista)
# ---------------------------------------------------------------------------

def album_canciones_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    album = get_object_or_404(Album, idalbum=pk, idartista=artista_id)
    canciones = Cancion.objects.filter(idalbum=pk).select_related('idgenero')

    return render(request, 'streaming/album_canciones.html', {
        'album': album,
        'canciones': canciones,
    })


def crear_cancion_view(request, id_album):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    album = get_object_or_404(Album, idalbum=id_album, idartista=artista_id)
    generos = Genero.objects.all()
    albums = Album.objects.filter(idartista=artista_id)

    form = CancionForm(request.POST or None, generos=generos, albums=albums)

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO CancionesLogica.Cancion
                       (nombreCancion, duracion, idAlbum, idGenero)
                       VALUES (%s, %s, %s, %s)""",
                    [
                        form.cleaned_data['nombre_cancion'],
                        form.cleaned_data['duracion'],
                        form.cleaned_data['id_album'],
                        form.cleaned_data['id_genero'],
                    ]
                )
            messages.success(request, "Canción agregada.")
            return redirect('album_canciones', pk=id_album)
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/cancion_form.html', {
        'form': form, 'accion': 'Crear', 'album': album
    })


def editar_cancion_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    artista_id = request.session.get('artista_id')
    cancion = get_object_or_404(Cancion, idcancion=pk)
    album = cancion.idalbum
    generos = Genero.objects.all()
    albums = Album.objects.filter(idartista=artista_id)

    form = CancionForm(
        request.POST or None,
        generos=generos,
        albums=albums,
        initial={
            'nombre_cancion': cancion.nombrecancion,
            'duracion': str(cancion.duracion) if cancion.duracion else '',
            'id_genero': cancion.idgenero_id,
            'id_album': cancion.idalbum_id,
        }
    )

    if request.method == 'POST' and form.is_valid():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE CancionesLogica.Cancion
                       SET nombreCancion = %s, duracion = %s, idAlbum = %s, idGenero = %s
                       WHERE idCancion = %s""",
                    [
                        form.cleaned_data['nombre_cancion'],
                        form.cleaned_data['duracion'],
                        form.cleaned_data['id_album'],
                        form.cleaned_data['id_genero'],
                        pk,
                    ]
                )
            messages.success(request, "Canción actualizada.")
            return redirect('album_canciones', pk=album.idalbum)
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'streaming/cancion_form.html', {
        'form': form, 'accion': 'Editar', 'cancion': cancion, 'album': album
    })


def eliminar_cancion_view(request, pk):
    if _login_requerido(request) or _artista_requerido(request):
        return redirect('login')

    cancion = get_object_or_404(Cancion, idcancion=pk)
    id_album = cancion.idalbum_id

    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM dbo.likeCancion WHERE idCancion = %s", [pk])
                cursor.execute(
                    "DELETE FROM Playlists.PlaylistCancion WHERE idCancion = %s", [pk]
                )
                cursor.execute(
                    "DELETE FROM CancionesLogica.Cancion WHERE idCancion = %s", [pk]
                )
            messages.success(request, "Canción eliminada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('album_canciones', pk=id_album)


# ---------------------------------------------------------------------------
# Reproducción
# ---------------------------------------------------------------------------

def registrar_escucha_view(request, id_cancion):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    dispositivo = request.META.get('HTTP_USER_AGENT', 'Web Browser')[:25]

    if request.method == 'POST':
        with connection.cursor() as cursor:
            cursor.execute(
                "EXEC CancionesLogica.sp_RegistrarEscucha @idUsuario=%s, @idCancion=%s, @dispositivo=%s",
                [usuario_id, id_cancion, dispositivo]
            )
        messages.success(request, "¡Escucha registrada!")
    return redirect(request.META.get('HTTP_REFERER', 'index'))


# ---------------------------------------------------------------------------
# CRUD Admin (Persona)
# ---------------------------------------------------------------------------

def crear_persona_view(request):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('index')
    if request.method == 'POST':
        nueva_persona = Persona(
            idpersona=request.POST.get('idpersona'),
            nombre=request.POST.get('nombre'),
            apellido=request.POST.get('apellido'),
            genero=request.POST.get('genero'),
            password=request.POST.get('password'),
            paisorigen=request.POST.get('paisorigen'),
            fecharegistro=request.POST.get('fecharegistro'),
        )
        nueva_persona.save()
        messages.success(request, "Persona registrada.")
        return redirect('index')
    return render(request, 'streaming/form_persona.html', {'accion': 'Crear'})


def editar_persona_view(request, pk):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('index')
    persona = Persona.objects.get(idpersona=pk)
    if request.method == 'POST':
        persona.nombre = request.POST.get('nombre')
        persona.apellido = request.POST.get('apellido')
        persona.genero = request.POST.get('genero')
        persona.paisorigen = request.POST.get('paisorigen')
        persona.save()
        messages.success(request, "Registro actualizado.")
        return redirect('index')
    return render(request, 'streaming/form_persona.html', {'persona': persona, 'accion': 'Editar'})


def eliminar_persona_view(request, pk):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('index')
    if request.method == 'POST':
        persona = Persona.objects.get(idpersona=pk)
        persona.delete()
        messages.success(request, "Registro eliminado.")
    return redirect('index')


def reporte_artista_view(request):
    return render(request, 'streaming/reporte_artista.html')
