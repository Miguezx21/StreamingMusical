from django.db import models
import uuid


class Persona(models.Model):
    idpersona = models.IntegerField(db_column='idPersona', primary_key=True)
    nombre = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS')
    apellido = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS')
    fecharegistro = models.DateField(db_column='fechaRegistro', blank=True, null=True)
    genero = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    password = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    verificado = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    paisorigen = models.CharField(db_column='paisOrigen', max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    fechanacimiento = models.DateField(db_column='fechaNacimiento', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Persona'


class TipoSuscripcion(models.Model):
    idtiposuscripcion = models.AutoField(db_column='idTipoSuscripcion', primary_key=True)
    nombretipo = models.CharField(db_column='nombreTipo', max_length=50, blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Suscripciones].[TipoSuscripcion]'


class Usuario(models.Model):
    idusuario = models.AutoField(db_column='idUsuario', primary_key=True)
    idpersona = models.OneToOneField(Persona, db_column='idPersona', on_delete=models.CASCADE)
    email = models.CharField(max_length=100, unique=True, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    fecharegistro = models.DateField(db_column='fechaRegistro', blank=True, null=True)
    idtiposuscripcion = models.ForeignKey(
        TipoSuscripcion, db_column='idTipoSuscripcion',
        on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = '[UsuariosBase].[Usuario]'


class Artista(models.Model):
    idartista = models.AutoField(db_column='idArtista', primary_key=True)
    idpersona = models.OneToOneField(Persona, db_column='idPersona', on_delete=models.CASCADE)
    nombreartistico = models.CharField(db_column='nombreArtistico', max_length=100, blank=True, null=True)
    oyentesmensuales = models.IntegerField(db_column='oyentesMensuales', blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Artistas].[Artista]'


class Perfil(models.Model):
    idperfil = models.AutoField(db_column='idPerfil', primary_key=True)
    idusuario = models.OneToOneField(Usuario, db_column='idUsuario', on_delete=models.CASCADE)
    nombreusuario = models.CharField(db_column='nombreUsuario', max_length=50, blank=True, null=True)
    fotoperfil = models.CharField(db_column='fotoPerfil', max_length=255, blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True, null=True)
    fechanacimiento = models.DateField(db_column='fechaNacimiento', blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Perfiles].[Perfil]'


class Genero(models.Model):
    idgenero = models.AutoField(db_column='idGenero', primary_key=True)
    nombregenero = models.CharField(db_column='nombreGenero', max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Generos].[Genero]'


class Album(models.Model):
    idalbum = models.AutoField(db_column='idAlbum', primary_key=True)
    nombrealbum = models.CharField(db_column='nombreAlbum', max_length=100, blank=True, null=True)
    fechalanzamiento = models.DateField(db_column='fechaLanzamiento', blank=True, null=True)
    idartista = models.ForeignKey(Artista, db_column='idArtista', on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Albumes].[Album]'


class Cancion(models.Model):
    idcancion = models.AutoField(db_column='idCancion', primary_key=True)
    nombrecancion = models.CharField(db_column='nombreCancion', max_length=100, blank=True, null=True)
    duracion = models.TimeField(blank=True, null=True)
    idalbum = models.ForeignKey(Album, db_column='idAlbum', on_delete=models.CASCADE, blank=True, null=True)
    idgenero = models.ForeignKey(Genero, db_column='idGenero', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[CancionesLogica].[Cancion]'


class Playlist(models.Model):
    idplaylist = models.AutoField(db_column='idPlaylist', primary_key=True)
    nombreplaylist = models.CharField(db_column='nombrePlaylist', max_length=100, blank=True, null=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    idusuario = models.ForeignKey(Usuario, db_column='idUsuario', on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = '[Playlists].[Playlist]'


class PlaylistCancion(models.Model):
    idplaylistcancion = models.AutoField(db_column='idPlaylistCancion', primary_key=True)
    idplaylist = models.ForeignKey(Playlist, db_column='idPlaylist', on_delete=models.CASCADE)
    idcancion = models.ForeignKey(Cancion, db_column='idCancion', on_delete=models.CASCADE)
    fechaagregada = models.DateField(db_column='fechaAgregada', blank=True, null=True)

    class Meta:
        managed = False
        db_table = '[Playlists].[PlaylistCancion]'
        unique_together = [('idplaylist', 'idcancion')]


class Pagosuscripcion(models.Model):
    idpago = models.IntegerField(db_column='idPago', primary_key=True)
    fechapago = models.DateField(db_column='fechaPago')
    monto = models.FloatField(blank=True, null=True)
    metodopago = models.CharField(db_column='metodoPago', max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    estado = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idusuario = models.IntegerField(db_column='idUsuario')

    class Meta:
        managed = False
        db_table = 'PagoSuscripcion'


class Reproduccion(models.Model):
    idreproduccion = models.IntegerField(db_column='idReproduccion', primary_key=True)
    fechahora = models.DateTimeField(db_column='fechaHora', blank=True, null=True)
    dispositivo = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idusuario = models.IntegerField(db_column='idUsuario')
    idcancion = models.IntegerField(db_column='idCancion')
    duracionescuchada = models.BigIntegerField(db_column='duracionEscuchada')

    class Meta:
        managed = False
        db_table = 'Reproduccion'


class Likecancion(models.Model):
    idlike = models.IntegerField(db_column='idLike', primary_key=True)
    fechalike = models.DateField(db_column='fechaLike')
    idusuario = models.IntegerField(db_column='idUsuario')
    idcancion = models.IntegerField(db_column='idCancion')

    class Meta:
        managed = False
        db_table = 'likeCancion'


class Notificacion(models.Model):
    idnotificacion = models.IntegerField(db_column='idNotificacion', primary_key=True)
    mensaje = models.CharField(max_length=75, db_collation='SQL_Latin1_General_CP1_CI_AS')
    fechaenvio = models.DateField(db_column='fechaEnvio')
    tipo = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idpersona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='idPersona')

    class Meta:
        managed = False
        db_table = 'notificacion'


# Tabla gestionada por Django para recuperación de contraseña
class TokenRecuperacion(models.Model):
    email = models.EmailField(max_length=100)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        managed = True
        db_table = 'TokenRecuperacion'
