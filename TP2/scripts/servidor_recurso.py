"""Servidor HTTP local controlado: I/O real, 100 ms y 16 KiB por respuesta."""

import asyncio

from fastapi import FastAPI, Response

app = FastAPI()


@app.get("/recurso")
async def recurso():
    await asyncio.sleep(0.1)
    return Response(b"x" * 16384, media_type="application/octet-stream")
