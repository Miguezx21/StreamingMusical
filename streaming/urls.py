# streaming/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Autenticación
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('recuperar-password/', views.recuperar_password_view, name='recuperar_password'),
    path('reset-password/<uuid:token>/', views.reset_password_view, name='reset_password'),

    # Dashboard por rol
    path('dashboard/usuario/', views.dashboard_usuario_view, name='dashboard_usuario'),
    path('dashboard/artista/', views.dashboard_artista_view, name='dashboard_artista'),

    # Playlists (Usuario)
    path('playlist/nueva/', views.crear_playlist_view, name='crear_playlist'),
    path('playlist/editar/<int:pk>/', views.editar_playlist_view, name='editar_playlist'),
    path('playlist/eliminar/<int:pk>/', views.eliminar_playlist_view, name='eliminar_playlist'),
    path('playlist/<int:pk>/', views.playlist_detalle_view, name='playlist_detalle'),
    path('playlist/<int:pk>/agregar/<int:id_cancion>/', views.agregar_cancion_playlist_view, name='agregar_cancion_playlist'),
    path('playlist/<int:pk>/quitar/<int:id_cancion>/', views.quitar_cancion_playlist_view, name='quitar_cancion_playlist'),

    # Perfil artístico
    path('artista/perfil/', views.artista_editar_perfil_view, name='artista_editar_perfil'),

    # Álbumes (Artista)
    path('album/nuevo/', views.crear_album_view, name='crear_album'),
    path('album/editar/<int:pk>/', views.editar_album_view, name='editar_album'),
    path('album/eliminar/<int:pk>/', views.eliminar_album_view, name='eliminar_album'),
    path('album/<int:pk>/canciones/', views.album_canciones_view, name='album_canciones'),

    # Canciones (Artista)
    path('album/<int:id_album>/cancion/nueva/', views.crear_cancion_view, name='crear_cancion'),
    path('cancion/editar/<int:pk>/', views.editar_cancion_view, name='editar_cancion'),
    path('cancion/eliminar/<int:pk>/', views.eliminar_cancion_view, name='eliminar_cancion'),

    # Reproducciones
    path('escuchar/<int:id_cancion>/', views.registrar_escucha_view, name='registrar_escucha'),

    # Admin
    path('persona/nuevo/', views.crear_persona_view, name='crear_persona'),
    path('persona/editar/<int:pk>/', views.editar_persona_view, name='editar_persona'),
    path('persona/eliminar/<int:pk>/', views.eliminar_persona_view, name='eliminar_persona'),
    path('reporte-artista/', views.reporte_artista_view, name='reporte_artista'),
]
