"""Pruebas de contrato, concurrencia y liberación real de recursos."""

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter

import httpx
import pytest

from app.config import Configuracion
from app.main import crear_app


@asynccontextmanager
async def entorno(tmp_path, **opciones):
    api = crear_app(Configuracion(directorio_estado=tmp_path, **opciones))
    async with api.router.lifespan_context(api):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api), base_url="http://test",
        ) as cliente:
            yield cliente, api.state.gestor


async def crear(cliente, tipo="esperar", timeout=2, **parametros):
    respuesta = await cliente.post("/tareas", json={
        "tipo": tipo, "parametros": parametros or {"segundos": 0.01},
        "timeout": timeout,
    })
    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["estado"] == "pendiente"
    return respuesta.json()["id"]


async def esperar_estado(cliente, identificador, estados, plazo=3):
    async with asyncio.timeout(plazo):
        while True:
            tarea = (await cliente.get(f"/tareas/{identificador}")).json()
            if tarea["estado"] in estados:
                return tarea
            await asyncio.sleep(0.005)


async def test_creacion_consulta_hash_filtros_y_estadisticas(tmp_path):
    async with entorno(tmp_path) as (cliente, gestor):
        identificador = await crear(cliente, "hashear", texto="hola", iteraciones=3)
        tarea = await esperar_estado(cliente, identificador, {"completada"})
        digest = b"hola"
        for _ in range(3):
            digest = hashlib.sha256(digest).digest()
        assert tarea["resultado"]["sha256"] == digest.hex()
        assert tarea["duracion"] >= 0
        assert tarea["iniciada"] and tarea["finalizada"]
        assert len((await cliente.get("/tareas?estado=completada")).json()) == 1
        assert (await cliente.get("/tareas?estado=pendiente")).json() == []
        assert (await cliente.get("/tareas?offset=1")).json() == []
        stats = (await cliente.get("/estadisticas")).json()
        assert stats["total"] == sum(stats["por_estado"].values()) == 1
        assert stats["workers_ocupados"] == 0
        assert stats["tiempo_promedio_ejecucion"] == tarea["duracion"]
        assert (await cliente.delete(f"/tareas/{identificador}")).json()["estado"] == "completada"


async def test_post_inmediato_y_ejecucion_concurrente(tmp_path):
    async with entorno(tmp_path, workers=4) as (cliente, gestor):
        inicio = perf_counter()
        ids = [await crear(cliente, segundos=0.3) for _ in range(4)]
        assert perf_counter() - inicio < 0.2
        await asyncio.sleep(0.03)
        assert gestor.estadisticas()["workers_ocupados"] == 4
        await gestor.cola.join()
        assert perf_counter() - inicio < 0.9  # Secuencial requeriría 1.2 s.
        assert all(t.estado == "completada" for t in gestor.tareas.values())
        assert len(ids) == 4


async def test_cancelacion_pendiente_y_ejecutando(tmp_path):
    async with entorno(tmp_path, workers=1) as (cliente, gestor):
        primera = await crear(cliente, segundos=10, timeout=20)
        await esperar_estado(cliente, primera, {"ejecutando"})
        segunda = await crear(cliente, segundos=1)
        assert (await cliente.delete(f"/tareas/{segunda}")).json()["estado"] == "cancelada"
        assert (await cliente.delete(f"/tareas/{primera}")).json()["estado"] == "cancelada"
        await asyncio.wait_for(gestor.cola.join(), 1)
        assert gestor.tareas[segunda].iniciada is None
        assert not gestor.en_curso
        tercera = await crear(cliente)
        await esperar_estado(cliente, tercera, {"completada"})
        assert gestor.estadisticas()["workers_vivos"] == 1


@pytest.mark.parametrize("cancelar", [True, False])
async def test_cpu_cancelada_o_timeout_libera_executor(tmp_path, cancelar):
    async with entorno(tmp_path, workers=1, hilos_cpu=1) as (cliente, gestor):
        identificador = await crear(
            cliente, "hashear", texto="CPU", iteraciones=100_000_000,
            timeout=10 if cancelar else 0.04,
        )
        await esperar_estado(cliente, identificador, {"ejecutando"})
        await asyncio.sleep(0.02)
        inicio = perf_counter()
        assert (await cliente.get("/tareas")).status_code == 200
        assert perf_counter() - inicio < 0.5
        if cancelar:
            await cliente.delete(f"/tareas/{identificador}")
        tarea = await esperar_estado(cliente, identificador, {"cancelada", "fallida"})
        assert tarea["estado"] == ("cancelada" if cancelar else "fallida")
        if not cancelar:
            assert "Timeout" in tarea["error"]
        # join espera la liberación del worker, no solo el estado visible.
        await asyncio.wait_for(gestor.cola.join(), 1)
        assert not gestor.en_curso and not gestor.senales
        segunda = await crear(cliente, "hashear", texto="nuevo", iteraciones=1)
        await esperar_estado(cliente, segunda, {"completada"}, plazo=1)


async def test_timeout_espera(tmp_path):
    async with entorno(tmp_path) as (cliente, gestor):
        identificador = await crear(cliente, segundos=1, timeout=0.02)
        tarea = await esperar_estado(cliente, identificador, {"fallida"})
        assert "Timeout" in tarea["error"]
        assert gestor.estadisticas()["por_estado"]["fallida"] == 1


async def test_descargas_concurrentes_resultados_y_error_de_red(tmp_path):
    activos = 0
    maximo = 0

    async def responder(peticion):
        nonlocal activos, maximo
        activos += 1
        maximo = max(maximo, activos)
        try:
            await asyncio.sleep(0.03)
            if peticion.url.path == "/error":
                raise httpx.ConnectError("Red no disponible", request=peticion)
            return httpx.Response(404 if peticion.url.path == "/404" else 200,
                                  content=b"abc")
        finally:
            activos -= 1

    async with entorno(tmp_path) as (cliente, gestor):
        await gestor.cliente.aclose()
        gestor.cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
        identificador = await crear(cliente, "descargar", urls=[
            "http://local/ok", "http://local/404", "http://local/error",
        ])
        tarea = await esperar_estado(cliente, identificador, {"completada"})
        resultados = tarea["resultado"]["descargas"]
        assert maximo == 3 and activos == 0
        assert resultados[0]["codigo_http"] == 200
        assert resultados[0]["tamano_bytes"] == 3
        assert resultados[0]["segundos"] > 0
        assert resultados[1]["codigo_http"] == 404
        assert "ConnectError" in resultados[2]["error"]


@pytest.mark.parametrize("cancelar", [True, False])
async def test_cancelar_o_timeout_descargas_no_deja_hijas(tmp_path, cancelar):
    activos = 0

    async def responder(peticion):
        nonlocal activos
        activos += 1
        try:
            await asyncio.sleep(10)
            return httpx.Response(200)
        finally:
            activos -= 1

    async with entorno(tmp_path) as (cliente, gestor):
        await gestor.cliente.aclose()
        gestor.cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
        identificador = await crear(cliente, "descargar", urls=["http://local/a"] * 5,
                                   timeout=2 if cancelar else 0.05)
        async with asyncio.timeout(1):
            while activos < 5:
                await asyncio.sleep(0.005)
        if cancelar:
            await cliente.delete(f"/tareas/{identificador}")
        await asyncio.wait_for(gestor.cola.join(), 1)
        assert activos == 0
        assert gestor.tareas[identificador].estado == ("cancelada" if cancelar else "fallida")


async def test_excepcion_de_operacion_no_mata_worker(tmp_path, monkeypatch):
    from app import gestor as modulo
    original = modulo.ejecutar

    async def fallar(*args):
        raise RuntimeError("fallo provocado")

    async with entorno(tmp_path, workers=1) as (cliente, gestor):
        monkeypatch.setattr(modulo, "ejecutar", fallar)
        identificador = await crear(cliente)
        tarea = await esperar_estado(cliente, identificador, {"fallida"})
        assert "fallo provocado" in tarea["error"]
        monkeypatch.setattr(modulo, "ejecutar", original)
        siguiente = await crear(cliente)
        await esperar_estado(cliente, siguiente, {"completada"})
        assert gestor.estadisticas()["workers_vivos"] == 1


async def test_supervision_worker_interrumpido(tmp_path):
    async with entorno(tmp_path, workers=1) as (cliente, gestor):
        await asyncio.sleep(0)
        gestor.workers[0].cancel()
        await asyncio.sleep(0.02)
        assert gestor.reinicios_workers == 1
        identificador = await crear(cliente)
        await esperar_estado(cliente, identificador, {"completada"})


async def test_cancelacion_cuando_hija_ya_termino(tmp_path, monkeypatch):
    from app import gestor as modulo

    async with entorno(tmp_path, workers=1) as (cliente, gestor):
        async def completar_y_cancelar(*args):
            identificador = next(iter(gestor.en_curso))
            asyncio.get_running_loop().call_soon(gestor.cancelar, identificador)
            return {"valor": "resultado listo"}

        monkeypatch.setattr(modulo, "ejecutar", completar_y_cancelar)
        identificador = await crear(cliente)
        await asyncio.wait_for(gestor.cola.join(), 1)
        assert gestor.tareas[identificador].estado == "cancelada"
        assert gestor.tareas[identificador].resultado is None


async def test_validacion_no_encontrados_y_cola_llena(tmp_path):
    async with entorno(tmp_path, workers=1, capacidad_cola=1) as (cliente, gestor):
        assert (await cliente.get("/tareas/inexistente")).status_code == 404
        assert (await cliente.delete("/tareas/inexistente")).status_code == 404
        assert (await cliente.get("/tareas?estado=invalido")).status_code == 422
        assert (await cliente.post("/tareas", json={
            "tipo": "esperar", "parametros": {"segundos": -1},
        })).status_code == 422
        assert (await cliente.post("/tareas", json={
            "tipo": "descargar", "parametros": {"urls": ["file:///etc/passwd"]},
        })).status_code == 422
        await crear(cliente, segundos=10)
        await asyncio.sleep(0.01)
        await crear(cliente, segundos=10)
        respuesta = await cliente.post("/tareas", json={
            "tipo": "esperar", "parametros": {"segundos": 1},
        })
        assert respuesta.status_code == 503
        for identificador in gestor.tareas:
            gestor.cancelar(identificador)


async def test_apagado_plazo_volcado_y_deteccion(tmp_path, caplog):
    async with entorno(tmp_path, workers=1, plazo_apagado=0.03) as (cliente, gestor):
        await crear(cliente, segundos=10)
        await crear(cliente, segundos=10)
    archivos = list(tmp_path.glob("estado_*.json"))
    assert len(archivos) == 1
    contenido = json.loads(archivos[0].read_text())
    assert all(t["estado"] == "cancelada" for t in contenido["tareas"])
    assert all(worker.done() for worker in gestor.workers)
    assert not gestor.en_curso
    assert gestor.cliente.is_closed
    with caplog.at_level(logging.INFO):
        async with entorno(tmp_path) as (nuevo_cliente, nuevo_gestor):
            assert "Volcado anterior detectado" in caplog.text
            assert nuevo_gestor.tareas == {}


async def test_apagado_permite_terminar_y_rechaza_nuevas(tmp_path):
    async with entorno(tmp_path, plazo_apagado=1) as (cliente, gestor):
        identificador = await crear(cliente, segundos=0.04)
        cierre = asyncio.create_task(gestor.cerrar())
        await asyncio.sleep(0.01)
        respuesta = await cliente.post("/tareas", json={
            "tipo": "esperar", "parametros": {"segundos": 0},
        })
        assert respuesta.status_code == 503
        await cierre
        assert gestor.tareas[identificador].estado == "completada"
