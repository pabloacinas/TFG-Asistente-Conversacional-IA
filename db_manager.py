import sqlite3
import os
from datetime import datetime, timedelta
from itertools import combinations

class DBManager:
    """
    Gestor de base de datos SQLite con asignación dinámica de mesas.
    Controla el bloqueo de 1 hora por reserva.
    """
    def __init__(self, db_path, schema_path):
        self.db_path = db_path
        self.schema_path = schema_path
        self._inicializar_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _inicializar_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            self._migrar_tabla_reservas(conn)
            conn.commit()

    def _migrar_tabla_reservas(self, conn):
        """Aplica migraciones simples para instalaciones previas sin columnas nuevas."""
        cursor = conn.execute("PRAGMA table_info(reservas)")
        columnas = {fila[1] for fila in cursor.fetchall()}

        if "estado" not in columnas:
            conn.execute("ALTER TABLE reservas ADD COLUMN estado TEXT NOT NULL DEFAULT 'confirmada'")
        if "codigo_confirmacion" not in columnas:
            conn.execute("ALTER TABLE reservas ADD COLUMN codigo_confirmacion TEXT")
        if "confirmado_en" not in columnas:
            conn.execute("ALTER TABLE reservas ADD COLUMN confirmado_en TIMESTAMP")

        conn.execute("UPDATE reservas SET estado = 'confirmada' WHERE estado IS NULL OR estado = ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reservas_estado ON reservas(estado)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_reservas_codigo_confirmacion "
            "ON reservas(codigo_confirmacion) WHERE codigo_confirmacion IS NOT NULL"
        )

    def calcular_hora_fin(self, hora_inicio_str, horas_duracion=1):
        """Calcula el final del turno de reserva."""
        inicio = datetime.strptime(hora_inicio_str, "%H:%M")
        fin = inicio + timedelta(hours=horas_duracion)
        return fin.strftime("%H:%M")

    def _obtener_mesas_libres(self, fecha_iso, hora_inicio, exclude_reserva_id=None):
        """Devuelve todas las mesas libres para una franja horaria."""
        hora_fin = self.calcular_hora_fin(hora_inicio)

        query = """
            SELECT id, capacidad
            FROM mesas
            WHERE id NOT IN (
                SELECT mesa_id
                FROM reservas_mesas
                WHERE fecha = ?
                AND (hora_inicio < ? AND hora_fin > ?)
                {}
            )
            ORDER BY capacidad DESC, id ASC
        """.format("AND reserva_id != ?" if exclude_reserva_id else "")

        params = [fecha_iso, hora_fin, hora_inicio]
        if exclude_reserva_id:
            params.append(exclude_reserva_id)

        with self._get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            return [{"id": fila[0], "capacidad": fila[1]} for fila in cursor.fetchall()]

    def encontrar_combinacion_mesas_disponibles(self, fecha_iso, hora_inicio, personas, exclude_reserva_id=None):
        """
        Busca la mejor combinación de mesas libres que cubra el aforo solicitado.
        Criterio: menor exceso de capacidad y, a igualdad, menor número de mesas.
        """
        mesas_libres = self._obtener_mesas_libres(fecha_iso, hora_inicio, exclude_reserva_id)
        if not mesas_libres:
            return []

        mejor = None
        mejor_score = None

        for r in range(1, len(mesas_libres) + 1):
            for combo in combinations(mesas_libres, r):
                capacidad_total = sum(mesa["capacidad"] for mesa in combo)
                if capacidad_total < personas:
                    continue

                exceso = capacidad_total - personas
                score = (exceso, r)

                if mejor is None or score < mejor_score:
                    mejor = list(combo)
                    mejor_score = score

            if mejor_score is not None and mejor_score[0] == 0:
                # No puede existir mejor que capacidad exacta con ese o menor número de mesas.
                break

        return mejor or []

    def encontrar_mesa_disponible(self, fecha_iso, hora_inicio, personas):
        """
        Busca una mesa libre que quepa el número de personas.
        Utiliza lógica de solapamiento de intervalos:
        Una mesa está ocupada si (inicio_nueva < fin_existente) Y (fin_nueva > inicio_existente).
        """
        combinacion = self.encontrar_combinacion_mesas_disponibles(fecha_iso, hora_inicio, personas)
        if len(combinacion) == 1:
            return combinacion[0]
        return None

    def crear_reserva_con_mesa(self, fecha_iso, hora_inicio, personas, nombre, telefono, mesa_id):
        """Compatibilidad: inserta reserva con una mesa."""
        return self.crear_reserva_con_mesas(
            fecha_iso,
            hora_inicio,
            personas,
            nombre,
            telefono,
            [mesa_id],
        )

    def crear_reserva_con_mesas(self, fecha_iso, hora_inicio, personas, nombre, telefono, mesa_ids):
        """Inserta la reserva y la asignación de una o más mesas en una transacción."""
        if not mesa_ids:
            return False

        hora_fin = self.calcular_hora_fin(hora_inicio)

        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO reservas (fecha, hora, personas, nombre, telefono, estado) VALUES (?, ?, ?, ?, ?, 'confirmada')",
                    (fecha_iso, hora_inicio, personas, nombre, telefono)
                )
                reserva_id = cursor.lastrowid

                for mesa_id in mesa_ids:
                    conn.execute(
                        "INSERT INTO reservas_mesas (reserva_id, mesa_id, fecha, hora_inicio, hora_fin) VALUES (?, ?, ?, ?, ?)",
                        (reserva_id, mesa_id, fecha_iso, hora_inicio, hora_fin)
                    )

                conn.commit()
                mesas_txt = ", ".join(str(mid) for mid in mesa_ids)
                print(f"[DB] Mesas [{mesas_txt}] asignadas a {nombre} para las {hora_inicio}")
                return True
        except Exception as e:
            print(f"[DB] Error al grabar reserva con mesas: {e}")
            return False

    def crear_reserva_pendiente(self, fecha_iso, hora_inicio, personas, nombre, telefono, codigo_confirmacion):
        """Inserta una reserva en estado pendiente a la espera de confirmación por SMS."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO reservas (fecha, hora, personas, nombre, telefono, estado, codigo_confirmacion)
                    VALUES (?, ?, ?, ?, ?, 'pendiente', ?)
                    """,
                    (fecha_iso, hora_inicio, personas, nombre, telefono, codigo_confirmacion)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"[DB] Error al crear reserva pendiente: {e}")
            return None

    def confirmar_reserva_pendiente(self, codigo_confirmacion):
        """Confirma una reserva pendiente, asigna mesas y la marca como confirmada."""
        codigo = (codigo_confirmacion or "").strip().upper()
        if not codigo:
            return {"ok": False, "reason": "codigo_invalido"}

        try:
            with self._get_connection() as conn:
                fila = conn.execute(
                    """
                    SELECT id, fecha, hora, personas, nombre, telefono
                    FROM reservas
                    WHERE codigo_confirmacion = ? AND estado = 'pendiente'
                    """,
                    (codigo,)
                ).fetchone()

                if not fila:
                    return {"ok": False, "reason": "no_encontrada"}

                reserva_id, fecha_iso, hora_inicio, personas, nombre, telefono = fila
                mesas = self.encontrar_combinacion_mesas_disponibles(fecha_iso, hora_inicio, personas)
                if not mesas:
                    alternativas = self.buscar_huecos_alternativos(fecha_iso, hora_inicio, personas)
                    return {
                        "ok": False,
                        "reason": "sin_disponibilidad",
                        "alternativas": alternativas,
                    }

                hora_fin = self.calcular_hora_fin(hora_inicio)
                mesa_ids = [mesa["id"] for mesa in mesas]

                for mesa_id in mesa_ids:
                    conn.execute(
                        "INSERT INTO reservas_mesas (reserva_id, mesa_id, fecha, hora_inicio, hora_fin) VALUES (?, ?, ?, ?, ?)",
                        (reserva_id, mesa_id, fecha_iso, hora_inicio, hora_fin)
                    )

                cursor = conn.execute(
                    """
                    UPDATE reservas
                    SET estado = 'confirmada', confirmado_en = CURRENT_TIMESTAMP
                    WHERE id = ? AND estado = 'pendiente'
                    """,
                    (reserva_id,)
                )

                if cursor.rowcount == 0:
                    conn.rollback()
                    return {"ok": False, "reason": "ya_confirmada"}

                conn.commit()
                return {
                    "ok": True,
                    "reserva_id": reserva_id,
                    "fecha": fecha_iso,
                    "hora": hora_inicio,
                    "personas": personas,
                    "nombre": nombre,
                    "telefono": telefono,
                    "mesa_ids": mesa_ids,
                }
        except Exception as e:
            print(f"[DB] Error al confirmar reserva pendiente: {e}")
            return {"ok": False, "reason": "error"}

    def buscar_huecos_alternativos(self, fecha_iso, hora_original, personas):
        """Busca huecos donde haya combinación de mesas disponible."""
        formato_hora = "%H:%M"
        hora_dt = datetime.strptime(hora_original, formato_hora)
        huecos_disponibles = []
        
        for i in range(1, 7):  # solo hacia adelante
            nueva_hora_dt = hora_dt + timedelta(minutes=30 * i)
            nueva_hora = nueva_hora_dt.strftime(formato_hora)

            if self.encontrar_combinacion_mesas_disponibles(fecha_iso, nueva_hora, personas):
                huecos_disponibles.append(nueva_hora)
                if len(huecos_disponibles) >= 3:
                    break
                
        return huecos_disponibles

    def obtener_reserva_por_codigo(self, codigo_confirmacion):
        codigo = (codigo_confirmacion or "").strip().upper()
        if not codigo: return None
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                fila = conn.execute(
                    "SELECT * FROM reservas WHERE codigo_confirmacion = ? AND estado IN ('confirmada', 'pendiente')",
                    (codigo,)
                ).fetchone()
                return dict(fila) if fila else None
        except Exception as e:
            print(f"[DB] Error al obtener reserva por código: {e}")
            return None

    def obtener_reservas_por_nombre(self, nombre):
        if not nombre: return []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                filas = conn.execute(
                    "SELECT * FROM reservas WHERE nombre LIKE ? AND estado IN ('confirmada', 'pendiente') ORDER BY fecha ASC, hora ASC",
                    (f"%{nombre.strip()}%",)
                ).fetchall()
                return [dict(f) for f in filas]
        except Exception as e:
            print(f"[DB] Error al obtener reservas por nombre: {e}")
            return []

    def cancelar_reserva(self, reserva_id):
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE reservas SET estado = 'cancelada' WHERE id = ?", (reserva_id,))
                conn.execute("DELETE FROM reservas_mesas WHERE reserva_id = ?", (reserva_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DB] Error al cancelar reserva: {e}")
            return False

    def preparar_modificacion_reserva(self, reserva_id, nueva_fecha, nueva_hora, nuevas_personas, nuevo_codigo):
        """
        Pasa la reserva a 'pendiente' con los nuevos datos y el nuevo código.
        Libera las mesas antiguas para que se puedan reasignar después al confirmar.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE reservas 
                    SET fecha = ?, hora = ?, personas = ?, estado = 'pendiente', codigo_confirmacion = ?
                    WHERE id = ?
                    """,
                    (nueva_fecha, nueva_hora, nuevas_personas, nuevo_codigo, reserva_id)
                )
                conn.execute("DELETE FROM reservas_mesas WHERE reserva_id = ?", (reserva_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DB] Error al preparar modificacion: {e}")
            return False
