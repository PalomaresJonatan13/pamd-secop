"""Corre los tres comprobadores del dashboard contra las cifras de Spark sobre gold (T4.5, T4.6 y T4.7) y resume el resultado.

Cada uno compara el dashboard con un JSON que escribe un script de Spark dentro del contenedor (ver dashboard/README.md):
    comprobar_cifras.py     tarjetas y gráfico mensual        dashboard/verificacion/cifras_spark.json
    comprobar_rankings.py   rankings de entidades y contratistas   dashboard/verificacion/rankings_spark.json
    comprobar_geografia.py  departamentos y concentración     dashboard/verificacion/geografia_spark.json

Desde la raíz del repositorio:
    .venv\\Scripts\\python scripts\\comprobar_dashboard.py
Termina con error si alguno no coincide. Si cambian gold o las tablas de consumo, hay que regenerar los JSON (scripts/consultas_spark_*.py).
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
COMPROBADORES = ["comprobar_cifras.py", "comprobar_rankings.py", "comprobar_geografia.py"]

resumen = []
for nombre in COMPROBADORES:
    proceso = subprocess.run([sys.executable, str(SCRIPTS / nombre)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    salida = [linea for linea in proceso.stdout.strip().splitlines() if linea.strip()]
    ultima = salida[-1] if salida else "(sin salida)"
    resumen.append((nombre, proceso.returncode == 0, ultima))
    if proceso.returncode != 0:
        print(proceso.stdout)
        print(proceso.stderr[-2000:])

print()
for nombre, ok, ultima in resumen:
    print(f"{'OK     ' if ok else 'FALLA  '}{nombre:<24}{ultima}")
sys.exit(0 if all(ok for _, ok, _ in resumen) else 1)
