from reservas import GestorReservas
import unittest

g = GestorReservas()
g.procesar_turno("10/10/2026 a las 14 para 2")
print("ESTADO TRAS PASO 1:", g.estado)
g.procesar_turno("nombre: Pablo telefono: 612345678")
print("NOMBRE:", g.datos["nombre"])
print("TELEFONO:", g.datos["telefono"])
