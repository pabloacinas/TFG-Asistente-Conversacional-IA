import os
import sys

# Permite importar módulos del núcleo desde los tests tras la reestructuración.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUCLEO_PATH = os.path.join(PROJECT_ROOT, "NucleoAlchi")
if NUCLEO_PATH not in sys.path:
    sys.path.insert(0, NUCLEO_PATH)
