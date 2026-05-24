# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Pagosuscripcion(models.Model):
    idpago = models.IntegerField(db_column='idPago', primary_key=True)  # Field name made lowercase.
    fechapago = models.DateField(db_column='fechaPago')  # Field name made lowercase.
    monto = models.FloatField(blank=True, null=True)
    metodopago = models.CharField(db_column='metodoPago', max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idusuario = models.IntegerField(db_column='idUsuario')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'PagoSuscripcion'


class Persona(models.Model):
    idpersona = models.IntegerField(db_column='idPersona', primary_key=True)  # Field name made lowercase.
    nombre = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS')
    apellido = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS')
    fecharegistro = models.DateField(db_column='fechaRegistro', blank=True, null=True)  # Field name made lowercase.
    genero = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    password = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    verificado = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    paisorigen = models.CharField(db_column='paisOrigen', max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fechanacimiento = models.DateField(db_column='fechaNacimiento', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Persona'


class Reproduccion(models.Model):
    idreproduccion = models.IntegerField(db_column='idReproduccion', primary_key=True)  # Field name made lowercase.
    fechahora = models.DateTimeField(db_column='fechaHora', blank=True, null=True)  # Field name made lowercase.
    dispositivo = models.CharField(max_length=25, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idusuario = models.IntegerField(db_column='idUsuario')  # Field name made lowercase.
    idcancion = models.IntegerField(db_column='idCancion')  # Field name made lowercase.
    duracionescuchada = models.BigIntegerField(db_column='duracionEscuchada')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'Reproduccion'


class Likecancion(models.Model):
    idlike = models.IntegerField(db_column='idLike', primary_key=True)  # Field name made lowercase.
    fechalike = models.DateField(db_column='fechaLike')  # Field name made lowercase.
    idusuario = models.IntegerField(db_column='idUsuario')  # Field name made lowercase.
    idcancion = models.IntegerField(db_column='idCancion')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'likeCancion'


class Notificacion(models.Model):
    idnotificacion = models.IntegerField(db_column='idNotificacion', primary_key=True)  # Field name made lowercase.
    mensaje = models.CharField(max_length=75, db_collation='SQL_Latin1_General_CP1_CI_AS')
    fechaenvio = models.DateField(db_column='fechaEnvio')  # Field name made lowercase.
    tipo = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    idpersona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='idPersona')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'notificacion'
