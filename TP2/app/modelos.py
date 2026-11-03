"""Contratos de entrada y registro de estado en memoria."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Estado(str, Enum):
    pendiente = "pendiente"
    ejecutando = "ejecutando"
    completada = "completada"
    fallida = "fallida"
    cancelada = "cancelada"


TERMINALES = {Estado.completada, Estado.fallida, Estado.cancelada}


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ParametrosDescarga(Estricto):
    urls: list[HttpUrl] = Field(min_length=1, max_length=100)


class ParametrosHash(Estricto):
    texto: str = Field(max_length=100_000)
    iteraciones: int = Field(ge=1, le=100_000_000)


class ParametrosEspera(Estricto):
    segundos: float = Field(ge=0, le=3600)


class SolicitudBase(Estricto):
    timeout: float = Field(default=30, gt=0, le=3600)


class Descargar(SolicitudBase):
    tipo: Literal["descargar"]
    parametros: ParametrosDescarga


class Hashear(SolicitudBase):
    tipo: Literal["hashear"]
    parametros: ParametrosHash


class Esperar(SolicitudBase):
    tipo: Literal["esperar"]
    parametros: ParametrosEspera


Solicitud = Annotated[Descargar | Hashear | Esperar, Field(discriminator="tipo")]


class Tarea(BaseModel):
    id: str
    solicitud: Solicitud
    estado: Estado = Estado.pendiente
    creada: datetime = Field(default_factory=ahora)
    iniciada: datetime | None = None
    finalizada: datetime | None = None
    duracion: float | None = None
    espera_cola: float | None = None
    resultado: dict | None = None
    error: str | None = None
