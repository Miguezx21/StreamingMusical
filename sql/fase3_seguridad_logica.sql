-- =====================================================
-- PROYECTO: STREAMING MUSICAL - FASE 3 (SEGURIDAD Y LÓGICA) - CORREGIDO
-- AUTOR: EQUIPO DE TRABAJO (MIGUEL PEÑA Y GRUPO)
-- DIRIGIDO A: Geovanni Aucancela Soliz
-- =====================================================

USE master;
GO

-- 1. RE-ESTABLECIMIENTO DE BASE DE DATOS
IF EXISTS (SELECT * FROM sys.databases WHERE name = 'StreamingMusical')
BEGIN
    ALTER DATABASE StreamingMusical SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE StreamingMusical;
END
GO

CREATE DATABASE StreamingMusical;
GO

-- Forzamos a la sesión actual a cambiarse a la nueva base de datos antes de hacer nada más
USE StreamingMusical;
GO

-- 2. CREACIÓN DE ESQUEMAS EXPLÍCITOS
-- Ponemos GO después de cada bloque para asegurar que existan en el sistema antes de las tablas
CREATE SCHEMA Suscripciones;
GO
CREATE SCHEMA Discograficas;
GO
CREATE SCHEMA Generos;
GO
CREATE SCHEMA UsuariosBase;
GO
CREATE SCHEMA Perfiles;
GO
CREATE SCHEMA Artistas;
GO
CREATE SCHEMA Albumes;
GO
CREATE SCHEMA CancionesLogica;
GO
CREATE SCHEMA Playlists;
GO

-- 3. DEFINICIÓN DE TABLAS (MODELO PERSONA-USUARIO-ARTISTA)

-- Tablas base
CREATE TABLE dbo.Persona (
    idPersona INT NOT NULL PRIMARY KEY,
    nombre VARCHAR(25) NOT NULL,
    apellido VARCHAR(25) NOT NULL,
    fechaRegistro DATE,
    genero VARCHAR(20),
    password VARCHAR(50) NOT NULL,
    verificado VARCHAR(25),
    paisOrigen VARCHAR(25),
    fechaNacimiento DATE
);
GO

CREATE TABLE Suscripciones.TipoSuscripcion (
    idTipoSuscripcion INT NOT NULL IDENTITY PRIMARY KEY,
    nombreTipo VARCHAR(50),
    precio DECIMAL(10,2),
    descripcion VARCHAR(200)
);
GO

CREATE TABLE Generos.Genero (
    idGenero INT NOT NULL IDENTITY PRIMARY KEY,
    nombreGenero VARCHAR(50)
);
GO

CREATE TABLE Discograficas.Discografica (
    idDiscografica INT NOT NULL IDENTITY PRIMARY KEY,
    nombreDiscografica VARCHAR(100),
    pais VARCHAR(50)
);
GO

-- Entidades principales
CREATE TABLE UsuariosBase.Usuario (
    idUsuario INT NOT NULL IDENTITY PRIMARY KEY,
    idPersona INT NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255),
    fechaRegistro DATE,
    idTipoSuscripcion INT,
    CONSTRAINT FK_Usuario_Persona FOREIGN KEY (idPersona) REFERENCES dbo.Persona(idPersona),
    CONSTRAINT FK_Usuario_TipoSub FOREIGN KEY (idTipoSuscripcion) REFERENCES Suscripciones.TipoSuscripcion(idTipoSuscripcion)
);
GO

CREATE TABLE Artistas.Artista (
    idArtista INT NOT NULL IDENTITY PRIMARY KEY,
    idPersona INT NOT NULL UNIQUE,
    nombreArtistico VARCHAR(100),
    oyentesMensuales INT,
    CONSTRAINT FK_Artista_Persona FOREIGN KEY (idPersona) REFERENCES dbo.Persona(idPersona)
);
GO

CREATE TABLE Perfiles.Perfil (
    idPerfil INT NOT NULL IDENTITY PRIMARY KEY,
    idUsuario INT NOT NULL UNIQUE,
    nombreUsuario VARCHAR(50),
    fotoPerfil VARCHAR(255),
    pais VARCHAR(50),
    fechaNacimiento DATE,
    CONSTRAINT FK_Perfil_Usuario FOREIGN KEY (idUsuario) REFERENCES UsuariosBase.Usuario(idUsuario)
);
GO

-- Jerarquía musical
CREATE TABLE Albumes.Album (
    idAlbum INT NOT NULL IDENTITY PRIMARY KEY,
    nombreAlbum VARCHAR(100),
    fechaLanzamiento DATE,
    idArtista INT,
    CONSTRAINT FK_Album_Artista FOREIGN KEY (idArtista) REFERENCES Artistas.Artista(idArtista)
);
GO

CREATE TABLE CancionesLogica.Cancion (
    idCancion INT NOT NULL IDENTITY PRIMARY KEY,
    nombreCancion VARCHAR(100),
    duracion TIME,
    idAlbum INT,
    idGenero INT,
    CONSTRAINT FK_Cancion_Album FOREIGN KEY (idAlbum) REFERENCES Albumes.Album(idAlbum),
    CONSTRAINT FK_Cancion_Genero FOREIGN KEY (idGenero) REFERENCES Generos.Genero(idGenero)
);
GO

CREATE TABLE dbo.PagoSuscripcion (
    idPago INT NOT NULL PRIMARY KEY,
    fechaPago DATE NOT NULL,
    monto FLOAT,
    metodoPago VARCHAR(25),
    estado VARCHAR(20) DEFAULT 'pendiente',
    idUsuario INT NOT NULL,
    CONSTRAINT CK_EstadoPago CHECK (estado IN ('completado', 'pendiente')),
    CONSTRAINT FK_Pago_Usuario FOREIGN KEY (idUsuario) REFERENCES UsuariosBase.Usuario(idUsuario)
);
GO

-- Interacciones y transacciones
CREATE TABLE dbo.likeCancion (
    idLike INT NOT NULL PRIMARY KEY,
    fechaLike DATE NOT NULL,
    idUsuario INT NOT NULL,
    idCancion INT NOT NULL,
    CONSTRAINT FK_Like_Usuario FOREIGN KEY (idUsuario) REFERENCES UsuariosBase.Usuario(idUsuario),
    CONSTRAINT FK_Like_Cancion FOREIGN KEY (idCancion) REFERENCES CancionesLogica.Cancion(idCancion)
);

CREATE TABLE dbo.notificacion (
    idNotificacion INT NOT NULL PRIMARY KEY,
    mensaje VARCHAR(75) NOT NULL,
    fechaEnvio DATE NOT NULL,
    tipo VARCHAR(30),
    idPersona INT NOT NULL,
    CONSTRAINT CK_TipoNotif CHECK (tipo IN ('Hito de oyentes', 'Nuevo lanzamiento', 'Pago exitoso')),
    CONSTRAINT FK_Notif_Persona FOREIGN KEY (idPersona) REFERENCES dbo.Persona(idPersona)
);
GO

CREATE TABLE dbo.Reproduccion (
    idReproduccion INT NOT NULL PRIMARY KEY,
    fechaHora DATETIME,
    dispositivo VARCHAR(25),
    idUsuario INT NOT NULL,
    idCancion INT NOT NULL,
    duracionEscuchada BIGINT NOT NULL,
    CONSTRAINT FK_Repro_Usuario FOREIGN KEY (idUsuario) REFERENCES UsuariosBase.Usuario(idUsuario),
    CONSTRAINT FK_Repro_Cancion FOREIGN KEY (idCancion) REFERENCES CancionesLogica.Cancion(idCancion)
);

CREATE TABLE Playlists.Playlist (
    idPlaylist INT NOT NULL IDENTITY PRIMARY KEY,
    nombrePlaylist VARCHAR(100),
    descripcion VARCHAR(255), -- agregada en Fase 7 para paridad con el campo "descripcion" del schema Mongo
    idUsuario INT NOT NULL,
    CONSTRAINT FK_Playlist_Usuario FOREIGN KEY (idUsuario) REFERENCES UsuariosBase.Usuario(idUsuario)
);

-- Tabla intermedia PlaylistCancion
CREATE TABLE Playlists.PlaylistCancion (
    idPlaylistCancion INT NOT NULL IDENTITY PRIMARY KEY,
    idPlaylist INT NOT NULL,
    idCancion INT NOT NULL,
    fechaAgregada DATE DEFAULT GETDATE(),
    -- Apunta al nuevo esquema Playlists
    CONSTRAINT FK_PlaylistCancion_Playlist FOREIGN KEY (idPlaylist) REFERENCES Playlists.Playlist(idPlaylist),
    -- Apunta al nuevo esquema CancionesLogica (antiguo SCHEMA9)
    CONSTRAINT FK_PlaylistCancion_Cancion FOREIGN KEY (idCancion) REFERENCES CancionesLogica.Cancion(idCancion),
    CONSTRAINT UQ_PlaylistCancion UNIQUE (idPlaylist, idCancion)
);
GO

-- Índices
CREATE INDEX IX_Cancion_Nombre ON CancionesLogica.Cancion(nombreCancion);
CREATE INDEX IX_Reproduccion_Fecha ON dbo.Reproduccion(fechaHora);
CREATE INDEX IX_Like_UsuarioCancion ON dbo.likeCancion (idUsuario, idCancion);
CREATE INDEX IX_Cancion_AlbumGenero ON CancionesLogica.Cancion (idAlbum, idGenero);
GO


-- 4. SEGURIDAD (DCL)
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'DMA_SA')
BEGIN
    CREATE LOGIN [DMA_SA] WITH PASSWORD = 'Password123!', DEFAULT_DATABASE=[StreamingMusical], CHECK_POLICY=OFF;
END
GO

CREATE USER [DMA_SA] FOR LOGIN [DMA_SA];
GO
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE TO [DMA_SA];
GO

-- 5. CARGA DE DATOS (MUESTRA TÉCNICA)
-- =====================================================
-- CARGA DE DATOS COMPLETA - ESQUEMAS EXPLÍCITOS
-- =====================================================

-- 1. PERSONAS (Esquema por defecto dbo)
INSERT INTO dbo.Persona (idPersona, nombre, apellido, fechaRegistro, genero, password, verificado, paisOrigen, fechaNacimiento)
VALUES
(1, 'Carlos', 'Mendoza', '2024-01-10', 'Masculino', 'pass123', 'Si', 'México', '1990-05-15'),
(2, 'Ana', 'Gómez', '2024-02-05', 'Femenino', 'ana456', 'Si', 'Colombia', '1988-11-22'),
(3, 'Luis', 'Ramírez', '2024-01-20', 'Masculino', 'luis789', 'Si', 'Argentina', '1995-03-10'),
(4, 'María', 'Fernández', '2024-02-18', 'Femenino', 'maria321', 'No', 'España', '2000-07-07'),
(5, 'Jorge', 'Pérez', '2024-03-01', 'Masculino', 'jorge654', 'Si', 'Chile', '1992-09-12'),
(6, 'Laura', 'Sánchez', '2024-03-15', 'Femenino', 'laura987', 'Si', 'Perú', '1994-12-25'),
(7, 'Diego', 'Castro', '2024-01-05', 'Masculino', 'diego147', 'Si', 'Ecuador', '1991-02-28'),
(8, 'Sofía', 'Rojas', '2024-02-27', 'Femenino', 'sofia258', 'No', 'Uruguay', '1998-06-14'),
(9, 'Pablo', 'Ortiz', '2024-03-10', 'Masculino', 'pablo369', 'Si', 'Bolivia', '1993-08-19'),
(10, 'Valentina', 'Navarro', '2024-03-20', 'Femenino', 'vale741', 'Si', 'Venezuela', '1997-10-30');
GO

-- 2. TIPO SUSCRIPCIÓN (Esquema Suscripciones)
INSERT INTO Suscripciones.TipoSuscripcion (nombreTipo, precio, descripcion)
VALUES
('Gratuito', 0.00, 'Con publicidad y limitaciones'),
('Premium Individual', 5.99, 'Sin anuncios, alta calidad'),
('Premium Familiar', 9.99, 'Hasta 5 cuentas');
GO

-- 3. USUARIOS (Esquema UsuariosBase)
INSERT INTO UsuariosBase.Usuario (idPersona, email, password, fechaRegistro, idTipoSuscripcion)
VALUES
(1, 'carlos.mendoza@email.com', 'hash_carlos', '2024-01-10', 2),
(2, 'ana.gomez@email.com', 'hash_ana', '2024-02-05', 1),
(3, 'luis.ramirez@email.com', 'hash_luis', '2024-01-20', 3),
(4, 'maria.fernandez@email.com', 'hash_maria', '2024-02-18', 1),
(5, 'jorge.perez@email.com', 'hash_jorge', '2024-03-01', 2);
GO

-- 4. PERFILES (Esquema Perfiles)
INSERT INTO Perfiles.Perfil (idUsuario, nombreUsuario, fotoPerfil, pais, fechaNacimiento)
VALUES
(1, 'carlos_m', 'carlos.jpg', 'México', '1990-05-15'),
(2, 'ana_g', 'ana.jpg', 'Colombia', '1988-11-22'),
(3, 'luis_r', 'luis.jpg', 'Argentina', '1995-03-10'),
(4, 'maria_f', 'maria.jpg', 'España', '2000-07-07'),
(5, 'jorge_p', 'jorge.jpg', 'Chile', '1992-09-12');
GO

-- 5. ARTISTAS (Esquema Artistas)
INSERT INTO Artistas.Artista (idPersona, nombreArtistico, oyentesMensuales)
VALUES
(6, 'Laura Sings', 3500000),
(7, 'Diego Mix', 1500000),
(8, 'Sofi Rock', 5800000),
(9, 'Pablo Sound', 2200000),
(10, 'Valentina Flow', 4100000);
GO

-- 6. GÉNEROS (Esquema Generos)
INSERT INTO Generos.Genero (nombreGenero)
VALUES ('Pop'), ('Rock'), ('Reggaetón'), ('Electrónica'), ('Balada');
GO

-- 7. ÁLBUMES (Esquema Albumes)
INSERT INTO Albumes.Album (nombreAlbum, fechaLanzamiento, idArtista)
VALUES
('Amanecer', '2024-01-15', 1),
('Noches de Ciudad', '2023-11-20', 2),
('Libertad', '2024-02-10', 3),
('Ritmos Latinos', '2023-09-05', 4),
('Flow Eterno', '2024-03-01', 5);
GO

-- 8. CANCIONES (Esquema CancionesLogica)
INSERT INTO CancionesLogica.Cancion (nombreCancion, duracion, idAlbum, idGenero)
VALUES
('Amanecer (Intro)', '00:03:45', 1, 1),
('Tu Mirada', '00:04:10', 1, 5),
('Dance All Night', '00:03:20', 2, 4),
('Mistery', '00:05:00', 2, 4),
('Ruge el Corazón', '00:03:55', 3, 2),
('Cielo Azul', '00:04:30', 3, 2),
('Bailando Sola', '00:03:15', 4, 3),
('La Fiesta', '00:03:40', 4, 3),
('Flow Perdido', '00:04:05', 5, 3),
('Eterno Amor', '00:04:50', 5, 5);
GO

-- 9. LIKES (Esquema por defecto dbo)
INSERT INTO dbo.likeCancion (idLike, fechaLike, idUsuario, idCancion)
VALUES
(1, '2024-03-10', 1, 1),
(2, '2024-03-11', 1, 3),
(3, '2024-03-12', 2, 5),
(4, '2024-03-13', 3, 7),
(5, '2024-03-14', 4, 9),
(6, '2024-03-15', 5, 2),
(7, '2024-03-16', 1, 6),
(8, '2024-03-17', 2, 8),
(9, '2024-03-18', 3, 10),
(10, '2024-03-19', 4, 4);
GO

-- 10. NOTIFICACIONES (Esquema por defecto dbo)
INSERT INTO dbo.notificacion (idNotificacion, mensaje, fechaEnvio, tipo, idPersona)
VALUES
(1, 'Bienvenido a Streaming Musical', '2024-01-10', 'Nuevo lanzamiento', 1),
(2, 'Tu suscripción se renueva en 3 días', '2024-03-28', 'Pago exitoso', 3),
(3, 'Nuevo álbum de Laura Sings: Amanecer', '2024-01-15', 'Nuevo lanzamiento', 6),
(4, 'Has alcanzado 1M de oyentes', '2024-02-20', 'Hito de oyentes', 6),
(5, 'Oferta especial: 2 meses gratis', '2024-03-01', 'Pago exitoso', 2);
GO

-- 11. PAGOS (Esquema por defecto dbo)
INSERT INTO dbo.PagoSuscripcion (idPago, fechaPago, monto, metodoPago, estado, idUsuario)
VALUES
(1, '2024-01-01', 5.99, 'Tarjeta Crédito', 'completado', 1),
(2, '2024-02-01', 5.99, 'PayPal', 'completado', 1),
(3, '2024-01-20', 0.00, NULL, 'pendiente', 2),
(4, '2024-01-05', 9.99, 'Transferencia', 'completado', 3),
(5, '2024-03-01', 5.99, 'Tarjeta Débito', 'completado', 5);
GO

-- 12. REPRODUCCIONES (Esquema por defecto dbo)
INSERT INTO dbo.Reproduccion (idReproduccion, fechaHora, dispositivo, idUsuario, idCancion, duracionEscuchada)
VALUES
(1, '2024-03-25 10:30:00', 'Móvil', 1, 1, 225),
(2, '2024-03-25 11:45:00', 'Web', 2, 3, 200),
(3, '2024-03-25 12:15:00', 'Tablet', 3, 5, 235),
(4, '2024-03-25 14:00:00', 'Móvil', 4, 7, 195),
(5, '2024-03-25 16:20:00', 'Web', 5, 9, 245),
(6, '2024-03-26 09:10:00', 'Móvil', 1, 2, 250),
(7, '2024-03-26 18:30:00', 'Móvil', 2, 4, 300),
(8, '2024-03-26 20:00:00', 'Web', 3, 6, 270),
(9, '2024-03-27 08:45:00', 'Tablet', 4, 8, 220),
(10, '2024-03-27 13:40:00', 'Móvil', 5, 10, 290);
GO

-- 13. PLAYLISTS (Esquema Playlists)
INSERT INTO Playlists.Playlist (nombrePlaylist, idUsuario)
VALUES
('Éxitos para entrenar', 1),
('Relax en casa', 2),
('Rock en español', 3),
('Perreo puro', 4),
('Baladas para recordar', 5);
GO

-- 14. PLAYLIST CANCION (Esquema Playlists)
INSERT INTO Playlists.PlaylistCancion (idPlaylist, idCancion, fechaAgregada)
VALUES
(1, 1, '2024-03-26'),
(1, 3, '2024-03-26'),
(1, 5, '2024-03-27'),
(2, 2, '2024-03-25'),
(2, 4, '2024-03-25'),
(3, 5, '2024-03-24'),
(3, 6, '2024-03-24'),
(4, 7, '2024-03-23'),
(4, 8, '2024-03-23'),
(5, 10, '2024-03-23');
GO


-- 6. OBJETOS PROGRAMABLES ADICIONALES

-- =====================================================
-- SECCIÓN 6: OBJETOS PROGRAMABLES (ESQUEMAS CORREGIDOS)
-- =====================================================

-- 1. Procedimiento: Registrar Escucha de Canción (Se asigna al esquema CancionesLogica)
CREATE OR ALTER PROCEDURE CancionesLogica.sp_RegistrarEscucha
    @idUsuario INT,
    @idCancion INT,
    @dispositivo VARCHAR(25)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @nextID INT = (SELECT ISNULL(MAX(idReproduccion), 0) + 1 FROM dbo.Reproduccion);

    INSERT INTO dbo.Reproduccion (idReproduccion, fechaHora, dispositivo, idUsuario, idCancion, duracionEscuchada)
    VALUES (@nextID, GETDATE(), @dispositivo, @idUsuario, @idCancion, 240);

    PRINT 'Reproducción procesada con éxito.';
END
GO

-- 2. Función Scalar: Calcular total de ingresos por usuario
CREATE OR ALTER FUNCTION dbo.fn_TotalPagadoUsuario (@idUsuario INT)
RETURNS DECIMAL(10,2)
AS
BEGIN
    DECLARE @Total DECIMAL(10,2);
    SELECT @Total = SUM(monto) FROM dbo.PagoSuscripcion WHERE idUsuario = @idUsuario AND estado = 'completado';
    RETURN ISNULL(@Total, 0);
END
GO

-- 3. Procedimiento: Reporte de Canciones por Artista
CREATE OR ALTER PROCEDURE CancionesLogica.sp_ReporteCancionesArtista
    @idArtista INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT a.nombreArtistico, al.nombreAlbum, c.nombreCancion, c.duracion
    FROM Artistas.Artista a
    JOIN Albumes.Album al ON a.idArtista = al.idArtista
    JOIN CancionesLogica.Cancion c ON al.idAlbum = c.idAlbum
    WHERE a.idArtista = @idArtista;
END
GO

-- 4. Trigger: Notificación Automática de Pago (Esquema por defecto dbo)
CREATE OR ALTER TRIGGER dbo.tr_NuevaNotificacionPago
ON dbo.PagoSuscripcion
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.notificacion (idNotificacion, mensaje, fechaEnvio, tipo, idPersona)
    SELECT (SELECT ISNULL(MAX(idNotificacion), 0) + 1 FROM dbo.notificacion),
           'Su pago fue procesado con éxito', GETDATE(), 'Pago exitoso', u.idPersona
    -- CORRECCIÓN: Se actualiza el JOIN para usar UsuariosBase.Usuario en vez de SCHEMA4
    FROM inserted i
    JOIN UsuariosBase.Usuario u ON i.idUsuario = u.idUsuario;
END
GO

-- 7. PRUEBAS UNITARIAS DOCUMENTADAS
PRINT '--- VALIDACIÓN 1: Creación de Objetos ---';
SELECT name, type_desc FROM sys.objects WHERE type IN ('P', 'FN', 'TR');

PRINT '--- VALIDACIÓN 2: Ejecución de Procedimiento ---';
EXEC CancionesLogica.sp_ReporteCancionesArtista @idArtista = 1;

PRINT '--- VALIDACIÓN 3: Verificación de Usuario DCL ---';
SELECT name FROM sys.database_principals WHERE name = 'DMA_SA';
GO

-- Verificación final
-- =====================================================
-- SECCIÓN 7: VERIFICACIÓN FINAL DE CARGA
-- =====================================================
USE StreamingMusical;
GO

SELECT
    (SELECT COUNT(*) FROM dbo.Persona) AS [Personas],
    (SELECT COUNT(*) FROM Suscripciones.TipoSuscripcion) AS [TiposSuscripcion],
    (SELECT COUNT(*) FROM UsuariosBase.Usuario) AS [Usuarios],
    (SELECT COUNT(*) FROM Perfiles.Perfil) AS [Perfiles],
    (SELECT COUNT(*) FROM Artistas.Artista) AS [Artistas],
    (SELECT COUNT(*) FROM Generos.Genero) AS [Generos],
    (SELECT COUNT(*) FROM Albumes.Album) AS [Albumes],
    (SELECT COUNT(*) FROM CancionesLogica.Cancion) AS [Canciones],
    (SELECT COUNT(*) FROM dbo.likeCancion) AS [Likes],
    (SELECT COUNT(*) FROM dbo.notificacion) AS [Notificaciones],
    (SELECT COUNT(*) FROM dbo.PagoSuscripcion) AS [Pagos],
    (SELECT COUNT(*) FROM dbo.Reproduccion) AS [Reproducciones],
    (SELECT COUNT(*) FROM Playlists.Playlist) AS [Playlists],
    (SELECT COUNT(*) FROM Playlists.PlaylistCancion) AS [PlaylistCanciones];
GO

PRINT '==================================================================';
PRINT ' Base de datos StreamingMusical creada y cargada correctamente. ';
PRINT '==================================================================';
GO
