"""Ejecutar: python -m scripts.medir --salida resultados/mediciones.json.

Usa HTTP por sockets y procesos separados. No depende de Internet para medir.
"""

import argparse
import asyncio
import json
from importlib.metadata import version
import os
import platform
import socket
import statistics
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import httpx

from app.operaciones import descargar_una


def puerto_libre():
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        return reserva.getsockname()[1]


@asynccontextmanager
async def servidor(modulo, directorio, **variables):
    puerto = puerto_libre()
    with (directorio / f"servidor_{puerto}.log").open("w") as registro:
        proceso = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "uvicorn", modulo, "--host", "127.0.0.1",
            "--port", str(puerto), "--log-level", "warning", "--no-access-log",
            env={**os.environ, "DIRECTORIO_ESTADO": str(directorio),
                 "WORKERS": "4", "HILOS_CPU": "2", **variables},
            stdout=registro, stderr=registro,
        )
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{puerto}", timeout=60, trust_env=False,
            ) as cliente:
                async with asyncio.timeout(15):
                    while True:
                        if proceso.returncode is not None:
                            raise RuntimeError("No arrancó Uvicorn; revisar logs")
                        try:
                            await cliente.get("/openapi.json")
                            break
                        except httpx.ConnectError:
                            await asyncio.sleep(0.03)
                yield cliente
        finally:
            if proceso.returncode is None:
                proceso.terminate()
                try:
                    await asyncio.wait_for(proceso.wait(), 10)
                except TimeoutError:
                    proceso.kill()
                    await proceso.wait()
                    raise RuntimeError("El servidor no completó el apagado")


async def terminar(cliente, ids):
    async with asyncio.timeout(120):
        while True:
            respuesta = await cliente.get("/tareas?limite=10000")
            respuesta.raise_for_status()
            tareas = {t["id"]: t for t in respuesta.json() if t["id"] in ids}
            if len(tareas) == len(ids) and all(
                t["estado"] in ("completada", "fallida", "cancelada")
                for t in tareas.values()
            ):
                assert all(t["estado"] == "completada" for t in tareas.values()), tareas
                return list(tareas.values())
            await asyncio.sleep(0.005)


async def medir_io(recurso, api, repeticiones):
    url = str(recurso.base_url) + "/recurso"
    series = []
    await descargar_una(recurso, url)  # Calentamiento, fuera de la medición.
    for _ in range(repeticiones):
        inicio = perf_counter()
        secuenciales = [await descargar_una(recurso, url) for _ in range(20)]
        secuencial = perf_counter() - inicio
        assert all(r["codigo_http"] == 200 and r["tamano_bytes"] == 16384
                   for r in secuenciales)
        inicio = perf_counter()
        respuesta = await api.post("/tareas", json={
            "tipo": "descargar", "parametros": {"urls": [url] * 20}, "timeout": 30,
        })
        respuesta.raise_for_status()
        tareas = await terminar(api, {respuesta.json()["id"]})
        concurrente = perf_counter() - inicio
        assert all(r["codigo_http"] == 200 and r["tamano_bytes"] == 16384
                   for r in tareas[0]["resultado"]["descargas"])
        series.append({"secuencial_s": secuencial, "concurrente_s": concurrente,
                       "speedup": secuencial / concurrente})
    return {"urls": 20, "retardo_servidor_s": 0.1, "bytes_por_url": 16384,
            "series": series,
            "secuencial_mediana_s": statistics.median(s["secuencial_s"] for s in series),
            "concurrente_mediana_s": statistics.median(s["concurrente_s"] for s in series),
            "speedup_mediana": statistics.median(s["speedup"] for s in series)}


async def medir_cpu(directorio, repeticiones, iteraciones):
    resultados = {}
    for modo in ("bloqueante", "executor"):
        series = []
        marcador = directorio / f"marca_{modo}"
        async with servidor("scripts.servidor_api_medicion:app", directorio,
                            MODO_CPU=modo, MARCADOR_CPU=str(marcador)) as api:
            for _ in range(repeticiones):
                marcador.unlink(missing_ok=True)
                post = asyncio.create_task(api.post("/tareas", json={
                    "tipo": "hashear", "parametros": {
                        "texto": "Computacion II", "iteraciones": iteraciones,
                    }, "timeout": 60,
                }))
                async with asyncio.timeout(10):
                    while not marcador.exists():
                        await asyncio.sleep(0.002)
                await asyncio.sleep(0.05)
                inicio = perf_counter()
                respuesta_get = await api.get("/tareas")
                latencia = perf_counter() - inicio
                respuesta_get.raise_for_status()
                respuesta_post = await post
                respuesta_post.raise_for_status()
                tareas = await terminar(api, {respuesta_post.json()["id"]})
                series.append({"get_tareas_s": latencia, "calculo_s": tareas[0]["duracion"]})
        resultados[modo] = {
            "series": series,
            "get_mediana_s": statistics.median(s["get_tareas_s"] for s in series),
        }
    resultados["iteraciones"] = iteraciones
    resultados["retardo_tras_marcador_s"] = 0.05
    return resultados


async def medir_pool(api, repeticiones):
    filas = []
    for cantidad in (1, 2, 4, 8, 16, 32):
        series = []
        for _ in range(repeticiones):
            inicio = perf_counter()
            respuestas = await asyncio.gather(*[
                api.post("/tareas", json={
                    "tipo": "esperar", "parametros": {"segundos": 0.2}, "timeout": 10,
                }) for _ in range(cantidad)
            ])
            for respuesta in respuestas:
                respuesta.raise_for_status()
            tareas = await terminar(api, {r.json()["id"] for r in respuestas})
            tiempo = perf_counter() - inicio
            latencias = [
                (datetime.fromisoformat(t["finalizada"]) -
                 datetime.fromisoformat(t["creada"])).total_seconds()
                for t in tareas
            ]
            series.append({"lote_s": tiempo, "tareas_por_s": cantidad / tiempo,
                           "latencia_media_s": statistics.mean(latencias),
                           "espera_cola_media_s": statistics.mean(t["espera_cola"] for t in tareas)})
        filas.append({"cantidad": cantidad, "series": series,
                      "lote_mediana_s": statistics.median(s["lote_s"] for s in series),
                      "tareas_por_s_mediana": statistics.median(s["tareas_por_s"] for s in series),
                      "latencia_media_mediana_s": statistics.median(s["latencia_media_s"] for s in series),
                      "espera_cola_media_mediana_s": statistics.median(s["espera_cola_media_s"] for s in series)})
    return {"workers": 4, "espera_por_tarea_s": 0.2, "filas": filas}


async def principal(argumentos):
    with tempfile.TemporaryDirectory(prefix="tp2-mediciones-") as temporal:
        directorio = Path(temporal)
        async with servidor("scripts.servidor_recurso:app", directorio) as recurso:
            async with servidor("app.main:app", directorio) as api:
                print("Midiendo 20 descargas secuenciales y concurrentes...", flush=True)
                io = await medir_io(recurso, api, argumentos.repeticiones)
                print("Midiendo saturación del pool...", flush=True)
                pool = await medir_pool(api, argumentos.repeticiones)
        print("Midiendo GET durante CPU sin/con executor...", flush=True)
        cpu = await medir_cpu(directorio, argumentos.repeticiones, argumentos.iteraciones)
    resultado = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "plataforma": platform.platform(),
        "cpus_logicas": os.cpu_count(), "repeticiones": argumentos.repeticiones,
        "versiones": {nombre: version(nombre) for nombre in ("fastapi", "httpx", "uvicorn")},
        "io": io, "cpu": cpu, "pool": pool,
    }
    argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.salida.write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("resultados/mediciones.json"))
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--iteraciones", type=int, default=3_000_000)
    argumentos = parser.parse_args()
    if argumentos.repeticiones < 1 or argumentos.iteraciones < 1:
        parser.error("Repeticiones e iteraciones deben ser positivas")
    asyncio.run(principal(argumentos))
