# TP1 - Monitor de Procesos en Linux

Trabajo práctico de Computación II desarrollado en Python sobre GNU/Linux.

El objetivo del proyecto es implementar un monitor de procesos que obtenga información real del sistema leyendo el filesystem `/proc`, utilizando procesos paralelos, señales del sistema operativo, configuración dinámica y ejecución mediante Docker.

---

## Objetivos del proyecto

El monitor permite observar distintos aspectos del sistema Linux:

- Resumen de procesos.
- Uso de memoria por proceso.
- File descriptors abiertos.
- Threads por proceso.
- Señales bloqueadas, ignoradas y capturadas.
- Información de scheduling.
- Información global del sistema.

Además, el programa implementa:

- Multiprocessing.
- Snapshot compartido entre procesos.
- Manejo de señales.
- Recarga de configuración en caliente.
- Ejecución en Docker.
- Tests automatizados.

---

## Estructura del proyecto

```text
TP1_monitoreo/
├── src/
│   ├── analizadores/
│   │   ├── resumen.py
│   │   ├── memoria.py
│   │   ├── fds.py
│   │   ├── threads.py
│   │   ├── senales.py
│   │   ├── scheduling.py
│   │   └── sistema.py
│   ├── configuracion.py
│   ├── display.py
│   ├── main.py
│   ├── procfs.py
│   ├── recolector.py
│   └── senales.py
├── tests/
│   └── test_procfs.py
├── config.json
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── .gitignore