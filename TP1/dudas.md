# Dudas, decisiones y aclaraciones del TP1

Durante el desarrollo del trabajo práctico se tomaron distintas decisiones técnicas relacionadas con la lectura de información del sistema Linux, el uso de procesos paralelos, señales y Docker.

---

## 1. Lectura desde `/proc`

La principal decisión fue obtener la información del sistema directamente desde el filesystem `/proc`.

Se decidió no depender de comandos externos como `ps`, `top` o `htop`, porque el objetivo del trabajo es comprender cómo Linux expone información interna de procesos, memoria, threads, señales y scheduling.

Los archivos más utilizados fueron:

* `/proc`
* `/proc/<pid>/status`
* `/proc/<pid>/stat`
* `/proc/<pid>/cmdline`
* `/proc/<pid>/fd`
* `/proc/<pid>/task`
* `/proc/stat`
* `/proc/meminfo`
* `/proc/loadavg`
* `/proc/uptime`

---

## 2. Procesos que desaparecen durante la lectura

Una dificultad encontrada fue que algunos procesos pueden finalizar mientras el programa los está leyendo.

Por ejemplo, puede existir un PID al momento de listar `/proc`, pero desaparecer antes de leer `/proc/<pid>/status`.

Para resolver esto, se implementó manejo de errores y validaciones. Si un proceso ya no existe o no se puede leer, simplemente se ignora y el monitor continúa funcionando.

---

## 3. Permisos de lectura

Algunos archivos dentro de `/proc` pueden no ser accesibles dependiendo del usuario, permisos del sistema o características del proceso.

Para evitar que el programa se detenga por un error de permisos, se manejan excepciones al leer archivos. De esta forma, el monitor puede seguir funcionando aunque no pueda acceder a toda la información de todos los procesos.

---

## 4. Uso de multiprocessing

Se decidió utilizar `multiprocessing` para separar el trabajo en varios procesos analizadores.

Cada analizador se encarga de una parte distinta del sistema:

* Resumen de procesos.
* Memoria.
* File descriptors.
* Threads.
* Señales.
* Scheduling.
* Sistema global.

Esto permite que cada módulo trabaje de forma independiente y actualice sus datos en paralelo.

---

## 5. Snapshot compartido

Para compartir información entre los analizadores y la interfaz, se utilizó un `Manager.dict`.

Cada analizador escribe sus resultados en una clave del snapshot global. La interfaz luego lee ese snapshot y muestra la vista seleccionada.

También se utilizó un `Lock` para evitar escrituras simultáneas sobre el snapshot compartido.

---

## 6. Señales implementadas

Se implementó manejo de señales UNIX para controlar el monitor durante la ejecución.

Las señales utilizadas fueron:

* `SIGINT`: salida ordenada con Ctrl+C.
* `SIGTERM`: salida ordenada mediante `kill`.
* `SIGHUP`: recarga de configuración desde `config.json`.
* `SIGUSR1`: generación de dump JSON del snapshot actual.
* `SIGUSR2`: alternar modo verbose.
* `SIGWINCH`: repintado por redimensionamiento de terminal.

---

## 7. Recarga de configuración

Se agregó un archivo `config.json` para controlar parámetros del monitor sin modificar el código fuente.

Entre los parámetros configurables se encuentran:

* Intervalo de refresco.
* Cantidad de procesos mostrados en resumen.
* Cantidad de procesos mostrados en memoria.
* Límites para file descriptors.
* Límites para threads.
* Límites para señales.
* Límites para scheduling.

La señal `SIGHUP` permite recargar esta configuración sin cerrar el programa.

---

## 8. Docker

Se decidió incluir Docker para asegurar que el trabajo pueda ejecutarse en un entorno Linux controlado.

El monitor puede ejecutarse con:

```bash
docker compose run --rm monitor
```

Esta forma permite usar la TUI interactiva y cambiar de vistas con las teclas `1` a `7`.

---

## 9. Tests

Se agregaron tests con `pytest` para validar funciones principales del proyecto.

Los tests verifican que:

* Se puedan listar PIDs desde `/proc`.
* El PID 1 tenga campos básicos.
* La función de resumen respete límites.
* La configuración se cargue correctamente.

Los tests se ejecutan con:

```bash
docker compose run --rm monitor pytest -q
```

---

## 10. Aclaración final

El monitor desarrollado no busca reemplazar herramientas como `top` o `htop`, sino demostrar el funcionamiento interno de Linux leyendo directamente desde `/proc`.

El trabajo permite integrar conceptos de sistemas operativos, procesos, señales, concurrencia, Docker y testing automatizado.
