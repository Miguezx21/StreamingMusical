# streaming_mongo/urls.py
from django.urls import path
from . import views
 
app_name = 'mongo'
 
urlpatterns = [
    path('',                                          views.index,                        name='index'),
    path('login/',                                    views.login_view,                   name='login'),
    path('logout/',                                   views.logout_view,                  name='logout'),
    path('register/',                                 views.register_view,                name='register'),
    path('recuperar-password/',                       views.recuperar_password_view,      name='recuperar_password'),
    path('reset-password/<uuid:token>/',              views.reset_password_view,          name='reset_password'),
 
    path('dashboard/usuario/',                        views.dashboard_usuario_view,       name='dashboard_usuario'),
    path('dashboard/artista/',                        views.dashboard_artista_view,       name='dashboard_artista'),
 
    path('playlist/nueva/',                           views.crear_playlist_view,          name='crear_playlist'),
    path('playlist/editar/<str:pk>/',                 views.editar_playlist_view,         name='editar_playlist'),
    path('playlist/eliminar/<str:pk>/',               views.eliminar_playlist_view,       name='eliminar_playlist'),
    path('playlist/<str:pk>/',                        views.playlist_detalle_view,        name='playlist_detalle'),
    path('playlist/<str:pk>/agregar/<str:id_cancion>/', views.agregar_cancion_playlist_view, name='agregar_cancion_playlist'),
    path('playlist/<str:pk>/quitar/<str:id_cancion>/',  views.quitar_cancion_playlist_view,  name='quitar_cancion_playlist'),
 
    path('artista/perfil/',                           views.artista_editar_perfil_view,   name='artista_editar_perfil'),
 
    path('album/nuevo/',                              views.crear_album_view,             name='crear_album'),
    path('album/editar/<str:pk>/',                    views.editar_album_view,            name='editar_album'),
    path('album/eliminar/<str:pk>/',                  views.eliminar_album_view,          name='eliminar_album'),
    path('album/<str:pk>/canciones/',                 views.album_canciones_view,         name='album_canciones'),
 
    path('album/<str:id_album>/cancion/nueva/',       views.crear_cancion_view,           name='crear_cancion'),
    path('cancion/editar/<str:pk>/',                  views.editar_cancion_view,          name='editar_cancion'),
    path('cancion/eliminar/<str:pk>/',                views.eliminar_cancion_view,        name='eliminar_cancion'),
 
    path('escuchar/<str:id_cancion>/',                views.registrar_escucha_view,       name='registrar_escucha'),
 
    path('persona/nuevo/',                            views.crear_persona_view,           name='crear_persona'),
    path('persona/editar/<str:pk>/',                  views.editar_persona_view,          name='editar_persona'),
    path('persona/eliminar/<str:pk>/',                views.eliminar_persona_view,        name='eliminar_persona'),
    path('reporte-artista/',                          views.reporte_artista_view,         name='reporte_artista'),
]