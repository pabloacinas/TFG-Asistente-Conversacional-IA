-- Tabla de Reservas
CREATE TABLE IF NOT EXISTS reservas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATE NOT NULL,
    hora TIME NOT NULL,
    personas INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Mesas
CREATE TABLE IF NOT EXISTS mesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capacidad INTEGER NOT NULL
);

-- Relación Reservas-Mesas (Asignación física)
CREATE TABLE IF NOT EXISTS reservas_mesas (
    reserva_id INTEGER,
    mesa_id INTEGER,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    FOREIGN KEY(reserva_id) REFERENCES reservas(id),
    FOREIGN KEY(mesa_id) REFERENCES mesas(id)
);

CREATE INDEX IF NOT EXISTS idx_reservas_fecha_hora ON reservas(fecha, hora);
CREATE INDEX IF NOT EXISTS idx_asignacion_tiempo ON reservas_mesas(fecha, hora_inicio, hora_fin);
