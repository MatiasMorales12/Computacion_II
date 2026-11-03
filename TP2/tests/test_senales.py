"""Proceso Uvicorn real: SIGINT y SIGTERM deben activar lifespan y volcado."""

import asyncio
import json
import os
import signal
import socket
import sys
from pathlib import Path

import httpx
import pytest


@pytest.mark.parametrize("senal", [signal.SIGINT, signal.SIGTERM])
async def test_senal_real_exporta_y_cierra(tmp_path, senal):
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        puerto = reserva.getsockname()[1]
    proceso = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
        "--port", str(puerto), "--log-level", "warning",
        env={**os.environ, "DIRECTORIO_ESTADO": str(tmp_path), "PLAZO_APAGADO": "0.05"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{puerto}") as cliente:
            async with asyncio.timeout(10):
                while True:
                    try:
                        if (await cliente.get("/estadisticas")).status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.03)
            respuesta = await cliente.post("/tareas", json={
                "tipo": "hashear", "parametros": {"texto": "signal", "iteraciones": 100_000_000},
                "timeout": 30,
            })
            assert respuesta.status_code == 202
            await asyncio.sleep(0.05)
            proceso.send_signal(senal)
            salida, _ = await asyncio.wait_for(proceso.communicate(), 5)
            # Uvicorn puede reemitir la señal después de ejecutar el cierre.
            assert proceso.returncode in (0, -senal), salida.decode()
        archivos = list(Path(tmp_path).glob("estado_*.json"))
        assert len(archivos) == 1, salida.decode()
        contenido = json.loads(archivos[0].read_text())
        assert contenido["tareas"][0]["estado"] == "cancelada"
        assert contenido["estadisticas"]["workers_ocupados"] == 0
        assert "Estado exportado" in salida.decode()
    finally:
        if proceso.returncode is None:
            proceso.kill()
            await proceso.wait()
