-- 1. ROLES
CREATE TABLE Roles (
    id_rol INT IDENTITY(1,1) PRIMARY KEY,
    nombre_rol VARCHAR(50) NOT NULL
);

-- 2. USUARIOS
CREATE TABLE Usuarios (
    id_usuario INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(100) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL,
    id_rol INT NOT NULL,
    CONSTRAINT FK_Usuarios_Roles
    FOREIGN KEY (id_rol) REFERENCES Roles(id_rol)
);

-- 3. EDIFICIOS
CREATE TABLE Edificios (
    id_edificio INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    codigo VARCHAR(20) NOT NULL UNIQUE
);

-- 4. ESPACIOS (SALONES / LABS / SALAS)
CREATE TABLE Espacios (
    id_espacio INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    capacidad INT NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- aula, laboratorio, sala_conferencia
    estatus VARCHAR(20) DEFAULT 'Activo',
    id_edificio INT NOT NULL,
    CONSTRAINT FK_Espacios_Edificios
    FOREIGN KEY (id_edificio) REFERENCES Edificios(id_edificio)
    ON DELETE CASCADE
);

-- 5. CARRERAS
CREATE TABLE Carreras (
    id_carrera INT IDENTITY(1,1) PRIMARY KEY,
    nombre_carrera VARCHAR(100) NOT NULL,
    acronimo VARCHAR(20) NOT NULL
);

-- 6. GRUPOS
CREATE TABLE Grupos (
    id_grupo INT IDENTITY(1,1) PRIMARY KEY,
    nombre_grupo VARCHAR(50) NOT NULL,
    generacion_inicio INT NOT NULL,
    generacion_fin INT NULL,
    id_carrera INT NOT NULL,
    estatus VARCHAR(20) DEFAULT 'Activo',
    CONSTRAINT FK_Grupos_Carreras
    FOREIGN KEY (id_carrera) REFERENCES Carreras(id_carrera)
);

-- 7. PERIODOS (CUATRIMESTRES)
CREATE TABLE Periodos (
    id_periodo INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    activo BIT DEFAULT 0
);

-- 8. ASIGNACIONES (AULAS FIJAS POR GRUPO)
CREATE TABLE Asignaciones (
    id_asignacion INT IDENTITY(1,1) PRIMARY KEY,
    id_grupo INT NOT NULL,
    id_espacio INT NOT NULL,
    id_periodo INT NOT NULL,

    CONSTRAINT FK_Asignaciones_Grupos
    FOREIGN KEY (id_grupo) REFERENCES Grupos(id_grupo),

    CONSTRAINT FK_Asignaciones_Espacios
    FOREIGN KEY (id_espacio) REFERENCES Espacios(id_espacio),

    CONSTRAINT FK_Asignaciones_Periodos
    FOREIGN KEY (id_periodo) REFERENCES Periodos(id_periodo)
);

-- 9. HORARIOS (CLASES DIARIAS)
CREATE TABLE Horarios (
    id_horario INT IDENTITY(1,1) PRIMARY KEY,
    id_asignacion INT NOT NULL,
    dia_semana VARCHAR(15) NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,

    CONSTRAINT FK_Horarios_Asignaciones
    FOREIGN KEY (id_asignacion) REFERENCES Asignaciones(id_asignacion)
);

-- 10. RESERVAS (LABS / SALAS / EVENTOS)
CREATE TABLE Reservas (
    id_reserva INT IDENTITY(1,1) PRIMARY KEY,
    id_usuario INT NOT NULL,
    id_espacio INT NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    motivo VARCHAR(255),
    estado VARCHAR(20) DEFAULT 'Pendiente',

    CONSTRAINT FK_Reservas_Usuarios
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),

    CONSTRAINT FK_Reservas_Espacios
    FOREIGN KEY (id_espacio) REFERENCES Espacios(id_espacio)
);

-- 11. BLOQUEOS (MANTENIMIENTO)
CREATE TABLE Bloqueos (
    id_bloqueo INT IDENTITY(1,1) PRIMARY KEY,
    id_espacio INT NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    motivo VARCHAR(255),

    CONSTRAINT FK_Bloqueos_Espacios
    FOREIGN KEY (id_espacio) REFERENCES Espacios(id_espacio)
);