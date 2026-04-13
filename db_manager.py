import sqlite3
import os
from datetime import datetime, timedelta

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

    def encontrar_mesa_disponible(self, fecha_iso, hora_inicio, personas):
        """
        Busca una mesa libre que quepa el número de personas.
        Utiliza lógica de solapamiento de intervalos:
        Una mesa está ocupada si (inicio_nueva < fin_existente) Y (fin_nueva > inicio_existente).
        """
        hora_fin = self.calcular_hora_fin(hora_inicio)
        
        # SQL para encontrar mesas que NO tengan solapamientos
        query = """
            SELECT id, capacidad FROM mesas 
            WHERE capacidad >= ?
            AND id NOT IN (
                SELECT mesa_id FROM reservas_mesas 
                WHERE fecha = ? 
                AND (hora_inicio < ? AND hora_fin > ?)
            )
            ORDER BY capacidad ASC -- Elegir la mesa más ajustada al grupo
            LIMIT 1
        """
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, (personas, fecha_iso, hora_fin, hora_inicio))
            resultado = cursor.fetchone()
            if resultado:
                return {"id": resultado[0], "capacidad": resultado[1]}
        return None

    def crear_reserva_con_mesa(self, fecha_iso, hora_inicio, personas, nombre, telefono, mesa_id):
        """Inserta la reserva y la asignación de mesa en una transacción."""
        hora_fin = self.calcular_hora_fin(hora_inicio)
        
        try:
            with self._get_connection() as conn:
                # 1. Insertar en la tabla de reservas general
                cursor = conn.execute(
                    "INSERT INTO reservas (fecha, hora, personas, nombre, telefono) VALUES (?, ?, ?, ?, ?)",
                    (fecha_iso, hora_inicio, personas, nombre, telefono)
                )
                reserva_id = cursor.lastrowid
                
                # 2. Insertar en la tabla de asignación de mesa
                conn.execute(
                    "INSERT INTO reservas_mesas (reserva_id, mesa_id, fecha, hora_inicio, hora_fin) VALUES (?, ?, ?, ?, ?)",
                    (reserva_id, mesa_id, fecha_iso, hora_inicio, hora_fin)
                )
                conn.commit()
                print(f"✅ [DB] Mesa {mesa_id} asignada a {nombre} para las {hora_inicio}")
                return True
        except Exception as e:
            print(f"❌ [DB] Error al grabar reserva con mesa: {e}")
            return False

    def buscar_huecos_alternativos(self, fecha_iso, hora_original, personas):
        """Busca huecos donde haya una mesa física disponible."""
        formato_hora = "%H:%M"
        hora_dt = datetime.strptime(hora_original, formato_hora)
        huecos_disponibles = []
        
        for i in range(1, 7):  # solo hacia adelante
            nueva_hora_dt = hora_dt + timedelta(minutes=30 * i)
            nueva_hora = nueva_hora_dt.strftime(formato_hora)

            if self.encontrar_mesa_disponible(fecha_iso, nueva_hora, personas):
                huecos_disponibles.append(nueva_hora)
                if len(huecos_disponibles) >= 3:
                    break
                
        return huecos_disponibles
