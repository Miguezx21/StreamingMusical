# streaming/views.py
from django.shortcuts import render, redirect
from django.db import connection  
from django.contrib import messages
from .models import Persona, Reproduccion, Pagosuscripcion

def login_view(request):
    if request.method == 'POST':
        usuario_ingresado = request.POST.get('username')
        password_ingresado = request.POST.get('password')
        
        try:
            persona = Persona.objects.get(nombre=usuario_ingresado)
            if persona.password == password_ingresado:
                request.session['usuario_id'] = persona.idpersona
                request.session['usuario_nombre'] = f"{persona.nombre} {persona.apellido}"
                
                # CORRECCIÓN: Se elimina el atajo del ID == 1. 
                # Ahora SOLO si se llama "Admin" (sin importar mayúsculas) será administrador.
                if persona.nombre.lower() == 'admin':
                    request.session['es_admin'] = True
                else:
                    request.session['es_admin'] = False
                    
                messages.success(request, f"¡Sesión iniciada como {persona.nombre}!")
                return redirect('index')
            else:
                messages.error(request, "Contraseña incorrecta.")
        except Persona.DoesNotExist:
            messages.error(request, "El usuario no se encuentra registrado.")
    return render(request, 'streaming/login.html')

def index(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return render(request, 'streaming/index.html')

    es_admin = request.session.get('es_admin', False)
    contexto = {'es_admin': es_admin}

    if es_admin:
        contexto['personas'] = Persona.objects.all()
    else:
        # CORRECCIÓN: Vinculamos los nombres a IDs reales que existan en tu SQL Server
        # Cambia estos números (1, 2, 3) si en tu tabla Cancion usaste otros IDs.
        contexto['canciones'] = [
            {'idcancion': 1, 'nombrecancion': 'Midnight Medieval Techno', 'album': 'Chivalry Beats', 'duracion': '3:45'},
            {'idcancion': 2, 'nombrecancion': 'Dark Age Bass', 'album': 'Feudal Rhythms', 'duracion': '4:12'},
            {'idcancion': 3, 'nombrecancion': 'Castle Rave Stomp', 'album': 'Chivalry Beats', 'duracion': '2:58'},
        ]
        contexto['suscripcion'] = Pagosuscripcion.objects.filter(idusuario=usuario_id).first()
        contexto['perfil'] = Persona.objects.filter(idpersona=usuario_id).first()

    return render(request, 'streaming/index.html', contexto)

def logout_view(request):
    request.session.flush()
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect('login')



def registrar_escucha_view(request, id_cancion):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
        
    dispositivo = request.META.get('HTTP_USER_AGENT', 'Web Browser')[:25]

    if request.method == 'POST':
        with connection.cursor() as cursor:
            # Ejecuta tu SP real de SQL Server mandando el ID del usuario activo
            cursor.execute(
                "EXEC CancionesLogica.sp_RegistrarEscucha @idUsuario=%s, @idCancion=%s, @dispositivo=%s",
                [usuario_id, id_cancion, dispositivo]
            )
        messages.success(request, "¡Disfrutando de la pista! Escucha registrada mediante SP en SQL Server.")
    return redirect('index')

# --- Vistas CRUD Protegidas para el Admin ---
def crear_persona_view(request):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado. Se requieren permisos de Administrador.")
        return redirect('index')
    if request.method == 'POST':
        nueva_persona = Persona(
            idpersona=request.POST.get('idpersona'),
            nombre=request.POST.get('nombre'),
            apellido=request.POST.get('apellido'),
            genero=request.POST.get('genero'),
            password=request.POST.get('password'),
            paisorigen=request.POST.get('paisorigen'),
            fecharegistro=request.POST.get('fecharegistro')
        )
        nueva_persona.save()
        messages.success(request, "Nuevo usuario registrado con éxito.")
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
        messages.success(request, "Registro actualizado en SQL Server.")
        return redirect('index')
    return render(request, 'streaming/form_persona.html', {'persona': persona, 'accion': 'Editar'})

def eliminar_persona_view(request, pk):
    if not request.session.get('es_admin'):
        messages.error(request, "Acceso denegado.")
        return redirect('index')
    if request.method == 'POST':
        persona = Persona.objects.get(idpersona=pk)
        persona.delete()
        messages.success(request, "Registro eliminado de la base de datos.")
    return redirect('index')

def reporte_artista_view(request):
    # (Mantén aquí tu código actual de reporte_artista_view sin cambios)
    return render(request, 'streaming/reporte_artista.html')