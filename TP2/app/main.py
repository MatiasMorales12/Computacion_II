"""API HTTP y lifespan: Uvicorn maneja SIGINT/SIGTERM y llama al cierre."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Query

from .config import Configuracion
from .gestor import Gestor, NoDisponible
from .modelos import Estado, Solicitud, Tarea

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def crear_app(config: Configuracion | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(api: FastAPI):
        gestor = Gestor(config or Configuracion.desde_entorno())
        api.state.gestor = gestor
        await gestor.iniciar()
        try:
            yield
        finally:
            await gestor.cerrar()

    api = FastAPI(title="TP2 — Plataforma de Tareas Distribuidas", lifespan=lifespan)

    @api.post("/tareas", status_code=202, response_model=Tarea)
    async def crear(solicitud: Solicitud):
        try:
            return api.state.gestor.crear(solicitud)
        except NoDisponible as exc:
            raise HTTPException(503, str(exc)) from exc

    @api.get("/tareas", response_model=list[Tarea])
    async def listar(estado: Estado | None = None,
                     limite: int = Query(default=1000, ge=1, le=10000),
                     offset: int = Query(default=0, ge=0)):
        tareas = [t for t in api.state.gestor.tareas.values()
                  if estado is None or t.estado == estado]
        return tareas[offset:offset + limite]

    def buscar(identificador: str) -> Tarea:
        try:
            return api.state.gestor.tareas[identificador]
        except KeyError as exc:
            raise HTTPException(404, "Tarea inexistente") from exc

    @api.get("/tareas/{identificador}", response_model=Tarea)
    async def consultar(identificador: str):
        return buscar(identificador)

    @api.delete("/tareas/{identificador}", response_model=Tarea)
    async def cancelar(identificador: str):
        buscar(identificador)
        return api.state.gestor.cancelar(identificador)

    @api.get("/estadisticas")
    async def estadisticas():
        return api.state.gestor.estadisticas()

    return api


app = crear_app()
