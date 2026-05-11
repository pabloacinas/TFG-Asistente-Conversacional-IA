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
            conn.commit()

    def calcular_hora_fin(self, hora_inicio_str, horas_duracion=1):
        """Calcula el final del turno de reserva."""
        inicio = datetime.strptime(hora_inicio_str, "%H:%M")
        fin = inicio + timedelta(hours=horas_duracion)
        return fin.strftime("%H:%M")

    def _obtener_mesas_libres(self, fecha_iso, hora_inicio):
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
            )
            ORDER BY capacidad DESC, id ASC
        """

        with self._get_connection() as conn:
            cursor = conn.execute(query, (fecha_iso, hora_fin, hora_inicio))
            return [{"id": fila[0], "capacidad": fila[1]} for fila in cursor.fetchall()]

    def encontrar_combinacion_mesas_disponibles(self, fecha_iso, hora_inicio, personas):
        """
        Busca la mejor combinación de mesas libres que cubra el aforo solicitado.
        Criterio: menor exceso de capacidad y, a igualdad, menor número de mesas.
        """
        mesas_libres = self._obtener_mesas_libres(fecha_iso, hora_inicio)
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
                    "INSERT INTO reservas (fecha, hora, personas, nombre, telefono) VALUES (?, ?, ?, ?, ?)",
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
                print(f"✅ [DB] Mesas [{mesas_txt}] asignadas a {nombre} para las {hora_inicio}")
                return True
        except Exception as e:
            print(f"❌ [DB] Error al grabar reserva con mesas: {e}")
            return False

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
