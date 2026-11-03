"""Trabajo I/O asíncrono y cálculo CPU con cancelación cooperativa."""

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import perf_counter

import httpx

from .modelos import Descargar, Esperar, Hashear, Solicitud


class CalculoCancelado(Exception):
    """El hilo confirmó que dejó de calcular."""


def hash_iterado(texto: str, iteraciones: int, detener: Event) -> dict:
    """SHA256 sobre el digest binario previo; chequeo cada 1024 iteraciones."""
    digest = texto.encode("utf-8")
    for numero in range(iteraciones):
        if numero % 1024 == 0 and detener.is_set():
            raise CalculoCancelado()
        digest = hashlib.sha256(digest).digest()
    return {"sha256": digest.hex(), "iteraciones": iteraciones}


async def descargar_una(cliente: httpx.AsyncClient, url: str) -> dict:
    inicio = perf_counter()
    try:
        # Streaming: no conservamos cuerpos completos en memoria.
        async with cliente.stream("GET", url) as respuesta:
            tamano = 0
            async for bloque in respuesta.aiter_bytes():
                tamano += len(bloque)
            return {
                "url": url, "codigo_http": respuesta.status_code,
                "tamano_bytes": tamano, "segundos": perf_counter() - inicio,
                "error": None,
            }
    except httpx.HTTPError as exc:
        return {
            "url": url, "codigo_http": None, "tamano_bytes": 0,
            "segundos": perf_counter() - inicio,
            "error": f"{type(exc).__name__}: {exc}",
        }


async def ejecutar(solicitud: Solicitud, cliente: httpx.AsyncClient,
                   executor: ThreadPoolExecutor, detener: Event) -> dict:
    if isinstance(solicitud, Esperar):
        await asyncio.sleep(solicitud.parametros.segundos)
        return {"segundos": solicitud.parametros.segundos}
    if isinstance(solicitud, Descargar):
        # TaskGroup cancela y espera todas las descargas hijas al cancelarse.
        async with asyncio.TaskGroup() as grupo:
            descargas = [
                grupo.create_task(descargar_una(cliente, str(url)))
                for url in solicitud.parametros.urls
            ]
        return {"descargas": [t.result() for t in descargas]}
    if isinstance(solicitud, Hashear):
        futuro = asyncio.get_running_loop().run_in_executor(
            executor, hash_iterado, solicitud.parametros.texto,
            solicitud.parametros.iteraciones, detener,
        )
        try:
            # Shield conserva el futuro para poder esperar la salida REAL del hilo.
            return await asyncio.shield(futuro)
        except asyncio.CancelledError:
            detener.set()
            try:
                await asyncio.shield(futuro)
            except CalculoCancelado:
                pass
            raise
    raise ValueError("Tipo de tarea desconocido")
