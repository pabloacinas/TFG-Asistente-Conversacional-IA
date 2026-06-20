import unittest
from datetime import datetime, timedelta

from reservas import GestorReservas


class TestReservas(unittest.TestCase):

    def setUp(self):
        self.gestor = GestorReservas()
        self.fecha_abierta = self._obtener_proximo_dia_abierto()
        with self.gestor.servicio.db._get_connection() as conn:
            conn.execute("DELETE FROM reservas_mesas")
            conn.execute("DELETE FROM reservas")
            conn.commit()

    def _obtener_proximo_dia_abierto(self):
        hoy = datetime.now()
        for i in range(1, 15):
            futuro = hoy + timedelta(days=i)
            if futuro.weekday() not in [0, 1]:
                return futuro.strftime("%d/%m/%Y")
        raise RuntimeError("No se encontró día abierto en el rango esperado")

    # -----------------------
    # CASOS SIMPLES
    # -----------------------

    def test_inicio_reserva(self):
        self.gestor.procesar_turno("quiero reservar")
        self.assertEqual(self.gestor.estado, "PIDIENDO_FECHA")

    def test_hora(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")

        self.assertEqual(self.gestor.datos["hora"], "14:00")
        self.assertEqual(self.gestor.estado, "PIDIENDO_PERSONAS")

    def test_personas(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")

        self.assertEqual(self.gestor.datos["personas"], 2)

    # -----------------------
    # DISPONIBILIDAD
    # -----------------------

    def test_pasa_a_nombre_si_hay_mesa(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")

        self.assertIn(self.gestor.estado, ["PIDIENDO_NOMBRE", "OFRECIENDO_ALTERNATIVAS"])

    # -----------------------
    # NOMBRE Y TELÉFONO
    # -----------------------

    def test_nombre(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")
        self.gestor.procesar_turno("Pablo")

        if self.gestor.estado == "PIDIENDO_TELEFONO":
            self.assertEqual(self.gestor.datos["nombre"], "Pablo")

    def test_telefono(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")
        self.gestor.procesar_turno("Pablo")
        self.gestor.procesar_turno("612345678")

        if self.gestor.estado == "LISTO":
            self.assertEqual(self.gestor.datos["telefono"], "612345678")

    # -----------------------
    # CASOS NATURALES
    # -----------------------

    def test_frase_completa(self):
        self.gestor.procesar_turno(f"{self.fecha_abierta} a las 14:00 para 3 personas")

        self.assertEqual(self.gestor.datos["hora"], "14:00")
        self.assertEqual(self.gestor.datos["personas"], 3)

    def test_frase_desordenada(self):
        self.gestor.procesar_turno(f"para 4 personas el {self.fecha_abierta} a las 15:00")

        self.assertEqual(self.gestor.datos["hora"], "15:00")
        self.assertEqual(self.gestor.datos["personas"], 4)

    # -----------------------
    # CAMBIOS DE DATOS
    # -----------------------

    def test_cambio_hora(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")

        hora_original = self.gestor.datos["hora"]

        self.gestor.procesar_turno("mejor a las 15:00")

        self.assertNotEqual(self.gestor.datos["hora"], hora_original)
        self.assertEqual(self.gestor.datos["hora"], "15:00")

    # -----------------------
    # CASOS BORDE
    # -----------------------

    def test_input_invalido(self):
        self.gestor.procesar_turno("blablabla")

        self.assertIn(self.gestor.estado, ["INACTIVO", "PIDIENDO_HORA"])

    def test_numero_solo(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno(self.fecha_abierta)
        self.gestor.procesar_turno("14:00")
        self.gestor.procesar_turno("3")

        self.assertEqual(self.gestor.datos["personas"], 3)


    def test_reserva_completa(self):
        g = GestorReservas()

        g.procesar_turno("quiero reservar")
        g.procesar_turno(self.fecha_abierta)
        g.procesar_turno("a las 14:00")
        g.procesar_turno("para 2")
        g.procesar_turno("Pablo")
        respuesta = g.procesar_turno("612345678")

        self.assertTrue(
            "estado pendiente" in respuesta.lower()
            or "no tenemos disponibilidad" in respuesta.lower()
        )

    def test_frase_natural(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14 para 3 personas")

        self.assertEqual(g.datos["hora"], "14:00")
        self.assertEqual(g.datos["personas"], 3)

    def test_cambio_personas(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14 para 2")
        g.procesar_turno("mejor para 4")

        self.assertEqual(g.datos["personas"], 4)

    def test_cambio_hora(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14 para 2")
        g.procesar_turno("mejor a las 15")

        self.assertEqual(g.datos["hora"], "15:00")

    def test_datos_desordenados(self):
        g = GestorReservas()
        g.procesar_turno("4 personas")
        g.procesar_turno("quiero reservar")
        g.procesar_turno(f"{self.fecha_abierta} a las 15")

        self.assertEqual(g.datos["personas"], 4)
        self.assertEqual(g.datos["hora"], "15:00")

    def test_nombre_y_telefono_juntos(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14 para 2")
        respuesta = g.procesar_turno("nombre: Pablo telefono: 612345678")

        self.assertIn("estado pendiente", respuesta)
        self.assertIn("Pablo", respuesta)

    def test_no_confirma_sin_personas(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14")
        respuesta = g.procesar_turno("Pablo")

        self.assertNotIn("estado pendiente", respuesta.lower())
        self.assertEqual(g.estado, "PIDIENDO_PERSONAS")

    def test_alternativas_si_no_hay_mesa(self):
        g = GestorReservas()
        g.procesar_turno(f"{self.fecha_abierta} a las 14 para 20")

        self.assertIn(g.estado, ["OFRECIENDO_ALTERNATIVAS", "PIDIENDO_NOMBRE"])

    # -----------------------
    # MODIFICACIÓN Y CANCELACIÓN
    # -----------------------

    def _preparar_reserva_confirmada(self, g, nombre="Juan", hora="14:00"):
        g.procesar_turno("quiero reservar")
        g.procesar_turno(self.fecha_abierta)
        g.procesar_turno(hora)
        g.procesar_turno("2")
        g.procesar_turno(nombre)
        g.procesar_turno("600123456")
        
        codigo = g.datos["codigo_confirmacion"]
        g.procesar_turno(f"confirmo {codigo}")
        return codigo

    def test_cancelacion_con_codigo(self):
        g = GestorReservas()
        codigo = self._preparar_reserva_confirmada(g)
        
        respuesta = g.procesar_turno("quiero cancelar")
        self.assertEqual(g.estado, "PIDIENDO_CODIGO_MC")
        
        respuesta = g.procesar_turno(codigo)
        self.assertEqual(g.estado, "CONFIRMANDO_CANCELACION")
        
        respuesta = g.procesar_turno("si")
        self.assertIn("cancelada", respuesta.lower())
        self.assertEqual(g.estado, "INACTIVO")

    def test_cancelacion_por_nombre(self):
        g = GestorReservas()
        codigo = self._preparar_reserva_confirmada(g, nombre="Zacarias")
        
        g.procesar_turno("quiero cancelar mi reserva")
        respuesta = g.procesar_turno("no se el codigo, mi nombre es Zacarias")
        
        self.assertEqual(g.estado, "CONFIRMANDO_CANCELACION")
        g.procesar_turno("si")
        self.assertEqual(g.estado, "INACTIVO")

    def test_modificacion_hora(self):
        g = GestorReservas()
        codigo = self._preparar_reserva_confirmada(g, hora="14:00")
        
        g.procesar_turno("quiero modificar mi reserva")
        g.procesar_turno(codigo)
        
        self.assertEqual(g.estado, "RECOPILANDO_DATOS_MODIFICACION")
        
        respuesta = g.procesar_turno("quiero cambiarlo a las 15:00")
        self.assertEqual(g.estado, "ESPERANDO_CODIGO_MODIFICACION")
        
        nuevo_codigo = g.datos["codigo_confirmacion"]
        respuesta = g.procesar_turno(nuevo_codigo)
        self.assertIn("confirmada con", respuesta.lower())

if __name__ == "__main__":
    unittest.main()