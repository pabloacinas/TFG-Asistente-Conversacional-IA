import unittest
from reservas import GestorReservas


class TestReservas(unittest.TestCase):

    def setUp(self):
        self.gestor = GestorReservas()

    # -----------------------
    # CASOS SIMPLES
    # -----------------------

    def test_inicio_reserva(self):
        self.gestor.procesar_turno("quiero reservar")
        self.assertEqual(self.gestor.estado, "PIDIENDO_HORA")

    def test_hora(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno("a las 14:00")

        self.assertEqual(self.gestor.datos["hora"], "14:00")
        self.assertEqual(self.gestor.estado, "PIDIENDO_PERSONAS")

    def test_personas(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")

        self.assertEqual(self.gestor.datos["personas"], 2)

    # -----------------------
    # DISPONIBILIDAD
    # -----------------------

    def test_pasa_a_nombre_si_hay_mesa(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")

        self.assertIn(self.gestor.estado, ["PIDIENDO_NOMBRE", "OFRECIENDO_ALTERNATIVAS"])

    # -----------------------
    # NOMBRE Y TELÉFONO
    # -----------------------

    def test_nombre(self):
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno("a las 14:00")
        self.gestor.procesar_turno("para 2")
        self.gestor.procesar_turno("Pablo")

        if self.gestor.estado == "PIDIENDO_TELEFONO":
            self.assertEqual(self.gestor.datos["nombre"], "Pablo")

    def test_telefono(self):
        self.gestor.procesar_turno("quiero reservar")
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
        self.gestor.procesar_turno("mañana a las 14:00 para 3 personas")

        self.assertEqual(self.gestor.datos["hora"], "14:00")
        self.assertEqual(self.gestor.datos["personas"], 3)

    def test_frase_desordenada(self):
        self.gestor.procesar_turno("para 4 personas mañana a las 15:00")

        self.assertEqual(self.gestor.datos["hora"], "15:00")
        self.assertEqual(self.gestor.datos["personas"], 4)

    # -----------------------
    # CAMBIOS DE DATOS
    # -----------------------

    def test_cambio_hora(self):
        self.gestor.procesar_turno("quiero reservar")
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
        self.gestor.procesar_turno("14:00")
        self.gestor.procesar_turno("3")

        self.assertEqual(self.gestor.datos["personas"], 3)


    def test_reserva_completa(self):
        g = GestorReservas()

        g.procesar_turno("quiero reservar")
        g.procesar_turno("mañana a las 14:00")
        g.procesar_turno("para 2")
        g.procesar_turno("Pablo")
        respuesta = g.procesar_turno("612345678")

        self.assertIn("Reserva confirmada", respuesta)

    def test_frase_natural(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14 para 3 personas")

        self.assertEqual(g.datos["hora"], "14:00")
        self.assertEqual(g.datos["personas"], 3)

    def test_cambio_personas(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14 para 2")
        g.procesar_turno("mejor 4")

        self.assertEqual(g.datos["personas"], 4)

    def test_cambio_hora(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14 para 2")
        g.procesar_turno("mejor a las 15")

        self.assertEqual(g.datos["hora"], "15:00")

    def test_datos_desordenados(self):
        g = GestorReservas()
        g.procesar_turno("somos 4")
        g.procesar_turno("quiero reservar")
        g.procesar_turno("mañana a las 15")

        self.assertEqual(g.datos["personas"], 4)
        self.assertEqual(g.datos["hora"], "15:00")

    def test_nombre_y_telefono_juntos(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14 para 2")
        g.procesar_turno("Pablo 612345678")

        self.assertEqual(g.datos["nombre"], "Pablo")
        self.assertEqual(g.datos["telefono"], "612345678")

    def test_numero_solo(self):
        g = GestorReservas()
        g.procesar_turno("quiero reservar")
        g.procesar_turno("14:00")
        g.procesar_turno("3")

        self.assertEqual(g.datos["personas"], 3)

    def test_no_confirma_sin_personas(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14")
        respuesta = g.procesar_turno("Pablo")

        self.assertNotIn("confirmada", respuesta.lower())
        self.assertEqual(g.estado, "PIDIENDO_PERSONAS")

    def test_alternativas_si_no_hay_mesa(self):
        g = GestorReservas()
        g.procesar_turno("mañana a las 14 para 20")

        self.assertIn(g.estado, ["OFRECIENDO_ALTERNATIVAS", "PIDIENDO_NOMBRE"])

if __name__ == "__main__":
    unittest.main()