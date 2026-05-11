import unittest
from datetime import datetime, timedelta
from reservas import GestorReservas

class TestHorarios(unittest.TestCase):

    def setUp(self):
        self.gestor = GestorReservas()

    def obtener_proximo_dia(self, nombre_dia):
        """
        Auxiliar para obtener una fecha que caiga en un día específico de la semana.
        Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
        """
        dias = {
            "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
        }
        objetivo = dias[nombre_dia.lower()]
        hoy = datetime.now()
        for i in range(1, 8):
            futuro = hoy + timedelta(days=i)
            if futuro.weekday() == objetivo:
                return futuro.strftime("%d/%m/%Y")
        return None

    # -----------------------
    # TEST HORARIOS COCINA
    # -----------------------

    def test_hora_comida_valida(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok}")
        self.gestor.procesar_turno("a las 14:00")
        self.assertEqual(self.gestor.datos["hora"], "14:00")
        self.assertNotEqual(self.gestor.estado, "PIDIENDO_HORA")

    def test_hora_comida_limite_inferior(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 13:00")
        self.assertEqual(self.gestor.datos["hora"], "13:00")

    def test_hora_comida_limite_superior(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 15:30")
        self.assertEqual(self.gestor.datos["hora"], "15:30")

    def test_hora_comida_invalida_tarde(self):
        # 16:00 está fuera (cierra 15:30)
        fecha_ok = self.obtener_proximo_dia("miercoles")
        respuesta = self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 16:00")
        self.assertIn("cocina está abierta", respuesta)
        self.assertIsNone(self.gestor.datos["hora"])

    def test_hora_cena_valida(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 21:00")
        self.assertEqual(self.gestor.datos["hora"], "21:00")

    def test_hora_cena_limite_inferior(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 20:30")
        self.assertEqual(self.gestor.datos["hora"], "20:30")

    def test_hora_cena_limite_superior(self):
        fecha_ok = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 23:00")
        self.assertEqual(self.gestor.datos["hora"], "23:00")

    def test_hora_cena_invalida_noche(self):
        # 23:30 está fuera (cierra 23:00)
        fecha_ok = self.obtener_proximo_dia("miercoles")
        respuesta = self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 23:30")
        self.assertIn("cocina está abierta", respuesta)
        self.assertIsNone(self.gestor.datos["hora"])

    def test_hora_invalida_entre_turnos(self):
        # 18:00 está entre comida y cena
        fecha_ok = self.obtener_proximo_dia("miercoles")
        respuesta = self.gestor.procesar_turno(f"quiero reservar el {fecha_ok} a las 18:00")
        self.assertIn("cocina está abierta", respuesta)
        self.assertIsNone(self.gestor.datos["hora"])

    # -----------------------
    # TEST DÍAS DE CIERRE
    # -----------------------

    def test_reserva_lunes_cerrado(self):
        fecha_lunes = self.obtener_proximo_dia("lunes")
        respuesta = self.gestor.procesar_turno(f"quiero reservar para el {fecha_lunes}")
        self.assertIn("permanece cerrado los lunes y martes", respuesta)
        self.assertIsNone(self.gestor.datos["fecha"])

    def test_reserva_martes_cerrado(self):
        fecha_martes = self.obtener_proximo_dia("martes")
        respuesta = self.gestor.procesar_turno(f"quiero reservar para el {fecha_martes}")
        self.assertIn("permanece cerrado los lunes y martes", respuesta)
        self.assertIsNone(self.gestor.datos["fecha"])

    def test_reserva_miercoles_abierto(self):
        fecha_miercoles = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno(f"quiero reservar para el {fecha_miercoles}")
        self.assertEqual(self.gestor.datos["fecha"], fecha_miercoles)

    def test_detecta_dia_suelto_en_frase(self):
        fecha_miercoles = self.obtener_proximo_dia("miercoles")
        self.gestor.procesar_turno("quiero reservar para el miercoles")
        self.assertEqual(self.gestor.datos["fecha"], fecha_miercoles)

    def test_detecta_dia_suelto_como_respuesta(self):
        fecha_jueves = self.obtener_proximo_dia("jueves")
        self.gestor.procesar_turno("quiero reservar")
        self.gestor.procesar_turno("jueves")
        self.assertEqual(self.gestor.datos["fecha"], fecha_jueves)

    # -----------------------
    # TEST ALTERNATIVAS
    # -----------------------

    def test_alternativas_dentro_de_horario(self):
        # Forzamos una búsqueda de alternativas.
        # Si pido para 100 personas a las 15:15, las alternativas (+30min, +60min...) 
        # deberían ser filtradas si exceden las 15:30.
        self.gestor.procesar_turno("mañana a las 15:15 para 100 personas")
        
        # 15:15 + 30min = 15:45 (Invalida)
        # Solo debería quedar 15:15 si se comprueba a sí misma, pero buscar_huecos_alternativos
        # en db_manager empieza en +30min.
        # Por tanto, la lista de alternativas debería estar vacía o solo con horas válidas.
        for alt in self.gestor.alternativas:
            self.assertTrue(self.gestor.es_hora_en_horario_cocina(alt), f"Alternativa {alt} fuera de horario")

if __name__ == "__main__":
    unittest.main()
