# streaming/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('persona/nuevo/', views.crear_persona_view, name='crear_persona'),
    path('persona/editar/<int:pk>/', views.editar_persona_view, name='editar_persona'),
    path('persona/eliminar/<int:pk>/', views.eliminar_persona_view, name='eliminar_persona'),
    path('escuchar/<int:id_cancion>/', views.registrar_escucha_view, name='registrar_escucha'),
    path('reporte-artista/', views.reporte_artista_view, name='reporte_artista'),
]