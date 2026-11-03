"""Smoke test HTTP contra la API levantada por Compose, usando sockets reales."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from time import perf_counter

import httpx

from scripts.medir import servidor, terminar


async def principal(url):
    async with httpx.AsyncClient(base_url=url, timeout=10, trust_env=False) as cliente:
        inicial = (await cliente.get("/estadisticas")).json()
        respuestas = await asyncio.gather(*[
            cliente.post("/tareas", json={
                "tipo": "esperar", "parametros": {"segundos": 10}, "timeout": 20,
            }) for _ in range(inicial["workers_configurados"] + 1)
        ])
        for respuesta in respuestas:
            assert respuesta.status_code == 202
        ids = [r.json()["id"] for r in respuestas]
        estados = (await cliente.get("/tareas?estado=pendiente")).json()
        assert any(t["id"] in ids for t in estados)
        for identificador in ids[::-1]:
            respuesta = await cliente.delete(f"/tareas/{identificador}")
            assert respuesta.json()["estado"] == "cancelada"
        cpu = await cliente.post("/tareas", json={
            "tipo": "hashear", "parametros": {"texto": "http", "iteraciones": 100_000_000},
            "timeout": 30,
        })
        await asyncio.sleep(0.08)
        inicio = perf_counter()
        assert (await cliente.get("/tareas")).status_code == 200
        latencia = perf_counter() - inicio
        assert (await cliente.delete(f"/tareas/{cpu.json()['id']}")).json()["estado"] == "cancelada"
        espera = await cliente.post("/tareas", json={
            "tipo": "esperar", "parametros": {"segundos": 2}, "timeout": 0.03,
        })
        async with asyncio.timeout(2):
            while True:
                tarea = (await cliente.get(f"/tareas/{espera.json()['id']}")).json()
                if tarea["estado"] == "fallida":
                    assert "Timeout" in tarea["error"]
                    break
                await asyncio.sleep(0.01)
        # Ejecutar este script dentro del contenedor api: comparte su loopback.
        with tempfile.TemporaryDirectory(prefix="tp2-http-") as temporal:
            async with servidor("scripts.servidor_recurso:app", Path(temporal)) as recurso:
                descarga = await cliente.post("/tareas", json={
                    "tipo": "descargar", "parametros": {
                        "urls": [str(recurso.base_url) + "/recurso"] * 3,
                    },
                })
                tareas = await terminar(cliente, {descarga.json()["id"]})
                assert all(r["codigo_http"] == 200 and r["tamano_bytes"] == 16384
                           for r in tareas[0]["resultado"]["descargas"])
        final = (await cliente.get("/estadisticas")).json()
        assert final["workers_ocupados"] == 0
        assert final["total"] == sum(final["por_estado"].values())
        resultado = {"resultado": "OK", "get_durante_cpu_s": latencia,
                     "estadisticas_finales": final}
        print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    asyncio.run(principal(parser.parse_args().url))
