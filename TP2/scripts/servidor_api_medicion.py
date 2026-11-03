"""Variante deliberadamente bloqueante SOLO para el experimento del curso.

Nunca se usa en Dockerfile ni en app.main. El marcador permite enviar el GET
desde otro proceso cuando sabemos que el cálculo ya comenzó.
"""

import os
from pathlib import Path

from app import gestor
from app.main import crear_app
from app.modelos import Hashear
from app.operaciones import hash_iterado

ejecutar_original = gestor.ejecutar


async def ejecutar_medicion(solicitud, cliente, executor, detener):
    if isinstance(solicitud, Hashear):
        Path(os.environ["MARCADOR_CPU"]).write_text("iniciado", encoding="utf-8")
        if os.environ.get("MODO_CPU") == "bloqueante":
            # Este es el error que queremos medir, aislado de la implementación.
            return hash_iterado(solicitud.parametros.texto,
                                solicitud.parametros.iteraciones, detener)
    return await ejecutar_original(solicitud, cliente, executor, detener)


gestor.ejecutar = ejecutar_medicion
app = crear_app()
