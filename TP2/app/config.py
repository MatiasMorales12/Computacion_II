"""Configuración por entorno; una sola instancia del servidor comparte la cola."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Configuracion:
    workers: int = 4
    hilos_cpu: int = 2
    capacidad_cola: int = 1000
    plazo_apagado: float = 5.0
    directorio_estado: Path = Path("datos")

    def __post_init__(self):
        if min(self.workers, self.hilos_cpu, self.capacidad_cola) < 1:
            raise ValueError("Workers, hilos y capacidad deben ser positivos")
        if self.plazo_apagado <= 0:
            raise ValueError("El plazo de apagado debe ser positivo")

    @classmethod
    def desde_entorno(cls):
        return cls(
            workers=int(os.getenv("WORKERS", "4")),
            hilos_cpu=int(os.getenv("HILOS_CPU", "2")),
            capacidad_cola=int(os.getenv("CAPACIDAD_COLA", "1000")),
            plazo_apagado=float(os.getenv("PLAZO_APAGADO", "5")),
            directorio_estado=Path(os.getenv("DIRECTORIO_ESTADO", "datos")),
        )
