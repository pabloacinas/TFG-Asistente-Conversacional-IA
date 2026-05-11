import os
import gc
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from db_manager import DBManager
from reservas import GestorReservas


class TestAsignacionMultiMesas(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_alchi.db")
        self.schema_path = os.path.join(os.path.dirname(__file__), "database", "schema.sql")

        self.db = DBManager(self.db_path, self.schema_path)
        self._seed_mesas()

    def tearDown(self):
        self.db = None
        gc.collect()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _seed_mesas(self):
        # Distribucion pedida: 2x2, 3x4, 1x6
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM reservas_mesas")
            conn.execute("DELETE FROM reservas")
            conn.execute("DELETE FROM mesas")
            conn.executemany(
                "INSERT INTO mesas (capacidad) VALUES (?)",
                [(2,), (2,), (4,), (4,), (4,), (6,)],
            )
            conn.commit()

    def _proximo_dia_abierto(self):
        hoy = datetime.now()
        for i in range(1, 15):
            futuro = hoy + timedelta(days=i)
            if futuro.weekday() not in [0, 1]:
                return futuro.strftime("%Y-%m-%d"), futuro.strftime("%d/%m/%Y")
        raise RuntimeError("No se encontro un dia abierto")

    def test_combinacion_9_personas(self):
        fecha_iso, _ = self._proximo_dia_abierto()
        combo = self.db.encontrar_combinacion_mesas_disponibles(fecha_iso, "14:00", 9)

        self.assertTrue(combo)
        self.assertEqual(len(combo), 2)

        capacidades = sorted([m["capacidad"] for m in combo])
        self.assertEqual(capacidades, [4, 6])

    def test_sin_capacidad_devuelve_vacio(self):
        fecha_iso, _ = self._proximo_dia_abierto()
        combo = self.db.encontrar_combinacion_mesas_disponibles(fecha_iso, "14:00", 30)
        self.assertEqual(combo, [])

    def test_crear_reserva_con_varias_mesas_bloquea_franja(self):
        fecha_iso, _ = self._proximo_dia_abierto()
        combo = self.db.encontrar_combinacion_mesas_disponibles(fecha_iso, "14:00", 13)
        mesa_ids = [m["id"] for m in combo]

        ok = self.db.crear_reserva_con_mesas(
            fecha_iso=fecha_iso,
            hora_inicio="14:00",
            personas=13,
            nombre="Grupo Grande",
            telefono="600000001",
            mesa_ids=mesa_ids,
        )

        self.assertTrue(ok)

        # A la misma hora ya no deberia haber capacidad para otro grupo de 13.
        combo2 = self.db.encontrar_combinacion_mesas_disponibles(fecha_iso, "14:00", 13)
        self.assertEqual(combo2, [])

    def test_huecos_alternativos_con_multi_mesa(self):
        fecha_iso, _ = self._proximo_dia_abierto()
        combo = self.db.encontrar_combinacion_mesas_disponibles(fecha_iso, "14:00", 13)
        mesa_ids = [m["id"] for m in combo]

        self.db.crear_reserva_con_mesas(
            fecha_iso=fecha_iso,
            hora_inicio="14:00",
            personas=13,
            nombre="Grupo Grande",
            telefono="600000002",
            mesa_ids=mesa_ids,
        )

        alternativas = self.db.buscar_huecos_alternativos(fecha_iso, "14:00", 13)
        self.assertIn("15:00", alternativas)

    def test_flujo_gestor_reservas_confirma_con_varias_mesas(self):
        _, fecha_humano = self._proximo_dia_abierto()

        gestor = GestorReservas(llm_client=None)
        gestor.servicio.db = self.db

        gestor.procesar_turno("quiero reservar")
        gestor.procesar_turno(fecha_humano)
        gestor.procesar_turno("14:00")
        gestor.procesar_turno("para 9")
        gestor.procesar_turno("Pablo")
        respuesta = gestor.procesar_turno("612345678")

        self.assertIn("Reserva confirmada", respuesta)
        self.assertGreaterEqual(len(gestor.ultima_mesas_asignadas), 2)


if __name__ == "__main__":
    unittest.main()
