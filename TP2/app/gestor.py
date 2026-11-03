"""Productor-consumidor, transiciones de estado y ciclo de vida de recursos."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import perf_counter
from uuid import uuid4

import httpx

from .config import Configuracion
from .modelos import Estado, Solicitud, TERMINALES, Tarea, ahora
from .operaciones import ejecutar

log = logging.getLogger(__name__)


class NoDisponible(Exception):
    pass


class Gestor:
    def __init__(self, config: Configuracion):
        self.config = config
        self.cola: asyncio.Queue[str] = asyncio.Queue(config.capacidad_cola)
        self.tareas: dict[str, Tarea] = {}
        self.workers: list[asyncio.Task] = []
        self.en_curso: dict[str, asyncio.Task] = {}
        self.senales: dict[str, Event] = {}
        self.aceptando = False
        self.cerrando = False
        self.cerrado = False
        self.reinicios_workers = 0
        self.inicio = perf_counter()

    async def iniciar(self):
        self.config.directorio_estado.mkdir(parents=True, exist_ok=True)
        anteriores = sorted(self.config.directorio_estado.glob("estado_*.json"))
        for archivo in anteriores:
            log.info("Volcado anterior detectado (no se restaura): %s", archivo)
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.hilos_cpu, thread_name_prefix="sha256",
        )
        self.cliente = httpx.AsyncClient(
            follow_redirects=True, timeout=15, trust_env=False,
            limits=httpx.Limits(max_connections=100),
        )
        for indice in range(self.config.workers):
            self._crear_worker(indice)
        self.aceptando = True

    def _crear_worker(self, indice: int):
        worker = asyncio.create_task(self._worker(), name=f"worker-{indice}")
        if indice < len(self.workers):
            self.workers[indice] = worker
        else:
            self.workers.append(worker)
        worker.add_done_callback(lambda terminado: self._supervisar(indice, terminado))

    def _supervisar(self, indice: int, worker: asyncio.Task):
        if worker.cancelled():
            error = "cancelación inesperada"
        else:
            error = worker.exception()
        if not self.cerrando:
            log.error("Worker %s terminó inesperadamente: %s; reiniciando", indice, error)
            self.reinicios_workers += 1
            self._crear_worker(indice)

    def crear(self, solicitud: Solicitud) -> Tarea:
        if not self.aceptando or self.cola.full():
            raise NoDisponible("Servidor apagándose o cola llena")
        tarea = Tarea(id=str(uuid4()), solicitud=solicitud)
        self.tareas[tarea.id] = tarea
        self.cola.put_nowait(tarea.id)
        return tarea

    def cancelar(self, identificador: str) -> Tarea:
        tarea = self.tareas[identificador]
        if tarea.estado not in TERMINALES:
            tarea.estado = Estado.cancelada
            tarea.finalizada = ahora()
            tarea.error = "Cancelada por solicitud o apagado"
            if identificador in self.en_curso:
                self.senales[identificador].set()
                self.en_curso[identificador].cancel()
        return tarea

    async def _worker(self):
        while True:
            identificador = await self.cola.get()
            tarea = self.tareas[identificador]
            try:
                if tarea.estado == Estado.cancelada:
                    continue
                await self._procesar(tarea)
            finally:
                self.cola.task_done()

    async def _procesar(self, tarea: Tarea):
        inicio = perf_counter()
        tarea.estado = Estado.ejecutando
        tarea.iniciada = ahora()
        tarea.espera_cola = (tarea.iniciada - tarea.creada).total_seconds()
        senal = Event()
        self.senales[tarea.id] = senal
        trabajo = asyncio.create_task(ejecutar(
            tarea.solicitud, self.cliente, self.executor, senal,
        ))
        self.en_curso[tarea.id] = trabajo
        try:
            resultado = await asyncio.wait_for(trabajo, tarea.solicitud.timeout)
            # DELETE pudo llegar cuando la hija ya terminó, antes de reanudarnos.
            if tarea.estado != Estado.cancelada:
                tarea.resultado = resultado
                tarea.estado = Estado.completada
        except TimeoutError:
            if tarea.estado != Estado.cancelada:
                tarea.estado = Estado.fallida
                tarea.error = f"Timeout de ejecución: {tarea.solicitud.timeout} s"
        except asyncio.CancelledError:
            # La cancelación de un trabajo no debe matar al consumidor de la cola.
            tarea.estado = Estado.cancelada
            tarea.error = tarea.error or "Worker interrumpido"
            if asyncio.current_task().cancelling():
                raise
        except Exception as exc:
            if tarea.estado != Estado.cancelada:
                tarea.estado = Estado.fallida
                tarea.error = f"{type(exc).__name__}: {exc}"
            log.exception("Falló tarea %s; el worker sigue disponible", tarea.id)
        finally:
            tarea.finalizada = ahora()
            tarea.duracion = perf_counter() - inicio
            self.en_curso.pop(tarea.id, None)
            self.senales.pop(tarea.id, None)

    def estadisticas(self) -> dict:
        totales = {estado.value: 0 for estado in Estado}
        for tarea in self.tareas.values():
            totales[tarea.estado.value] += 1
        duraciones = [t.duracion for t in self.tareas.values() if t.duracion is not None]
        esperas = [t.espera_cola for t in self.tareas.values() if t.espera_cola is not None]
        return {
            "total": len(self.tareas), "por_estado": totales,
            "tiempo_promedio_ejecucion": sum(duraciones) / len(duraciones) if duraciones else 0,
            "tiempo_promedio_cola": sum(esperas) / len(esperas) if esperas else 0,
            "workers_configurados": self.config.workers,
            "workers_vivos": sum(not w.done() for w in self.workers),
            "workers_ocupados": len(self.en_curso),
            "reinicios_workers": self.reinicios_workers,
            "entradas_cola": self.cola.qsize(),
            "aceptando": self.aceptando,
            "uptime_segundos": perf_counter() - self.inicio,
        }

    async def cerrar(self):
        if self.cerrado:
            return
        self.aceptando = False
        self.cerrando = True
        try:
            await asyncio.wait_for(self.cola.join(), self.config.plazo_apagado)
        except TimeoutError:
            log.warning("Plazo de apagado agotado; cancelando tareas restantes")
            for identificador in self.tareas:
                self.cancelar(identificador)
            # La cancelación cooperativa espera confirmación del hilo CPU.
            await self.cola.join()
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        await self.cliente.aclose()
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)
        contenido = {
            "exportado": ahora().isoformat(), "estadisticas": self.estadisticas(),
            "tareas": [t.model_dump(mode="json") for t in self.tareas.values()],
        }
        nombre = f"estado_{ahora().strftime('%Y%m%dT%H%M%S_%fZ')}.json"
        destino = self.config.directorio_estado / nombre
        await asyncio.to_thread(
            destino.write_text, json.dumps(contenido, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Estado exportado: %s", destino)
        self.cerrado = True
