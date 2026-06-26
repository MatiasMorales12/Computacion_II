from pathlib import Path
import sys

# Agregamos src al path para poder importar los modulos del proyecto.
RUTA_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(RUTA_SRC))

from procfs import listar_pids, resumen_proceso, listar_resumenes
from configuracion import cargar_configuracion


def test_listar_pids_devuelve_enteros():
    pids = listar_pids()

    assert isinstance(pids, list)
    assert len(pids) > 0
    assert all(isinstance(pid, int) for pid in pids)


def test_resumen_proceso_pid_1_tiene_campos_basicos():
    resumen = resumen_proceso(1)

    assert resumen is not None
    assert "pid" in resumen
    assert "ppid" in resumen
    assert "usuario" in resumen
    assert "estado" in resumen
    assert "threads" in resumen
    assert "rss_kb" in resumen
    assert "comando" in resumen


def test_listar_resumenes_respeta_limite():
    procesos = listar_resumenes(limite=5)

    assert isinstance(procesos, list)
    assert len(procesos) <= 5


def test_cargar_configuracion_devuelve_valores():
    config = cargar_configuracion()

    assert "refresh_interval" in config
    assert "limite_resumen" in config
    assert "limite_memoria" in config
    assert config["refresh_interval"] > 0