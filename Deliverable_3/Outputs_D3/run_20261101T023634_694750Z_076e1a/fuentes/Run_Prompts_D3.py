""" Python 3.10+, sin pip.

Desde PowerShell, en Deliverable_3:
    python Run_Prompts_D3.py --listar
    python Run_Prompts_D3.py --limite 1
    python Run_Prompts_D3.py

-Por defecto exige 21 TXT en Prompts_separados. --esperados 0 desactiva ese control.
-Las rutas relativas se interpretan desde la carpeta de ESTE script, no desde cwd.
-Cada ejecución crea una carpeta nueva en Outputs_D3; no sobrescribe otra corrida.
-No mide exactitud: VALIDADA significa aceptada por validadores y auditor del sistema.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import platform
import re
import sys
import time
import traceback
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import coordinador as c
import herramientas as h


BASE = Path(__file__).resolve().parent
ENCODING = "utf-8-sig"  # Lee también archivos UTF-8 con BOM de Windows.
FUENTES = ["Run_Prompts_D3.py", "coordinador.py", "herramientas.py", "traces_legibles.py",
           *c.ARCHIVOS_PROMPTS.values()]
COLUMNAS = [
    "caso", "archivo", "estado", "segundos", "llamadas_iniciadas",
    "respuestas_recibidas", "correcciones_aplicadas", "tokens_entrada_reportados",
    "tokens_salida_reportados", "suministros_confirmados", "suministros_condicionales",
    "requerimientos_operativos", "urgencia", "vista_4_disponible", "pendientes_revision",
]


def ahora():
    return datetime.now(timezone.utc).isoformat()


def huella(datos: bytes):
    return hashlib.sha256(datos).hexdigest()


def ruta_desde_script(valor):
    ruta = Path(valor).expanduser()
    return (BASE / ruta).resolve() if not ruta.is_absolute() else ruta.resolve()


def orden_natural(ruta):
    # Caso_2.txt antes que Caso_10.txt, sin exigir un patrón de nombres particular.
    return [(1, int(p)) if p.isdigit() else (0, p.casefold())
            for p in re.split(r"(\d+)", ruta.name)]


def descubrir_casos(carpeta, esperados=21, limite=None, caso=None):
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ValueError(f"No existe la carpeta de casos: {carpeta}")
    archivos = sorted((p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() == ".txt"),
                      key=lambda p: (orden_natural(p), p.name))
    if not archivos:
        raise ValueError(f"No hay archivos TXT en {carpeta}")
    if esperados and len(archivos) != esperados:
        raise ValueError(f"Se esperaban {esperados} TXT y se encontraron {len(archivos)}. "
                         "Revisa la carpeta o usa --esperados 0 para otro conjunto.")
    if caso:
        seleccion = [p for p in archivos if p.name.casefold() == caso.casefold()]
        if len(seleccion) != 1:
            raise ValueError("--caso debe coincidir con el nombre completo de un TXT, incluida su extensión.")
    else:
        if limite is not None and limite < 1:
            raise ValueError("--limite debe ser mayor que cero.")
        seleccion = archivos[:limite] if limite is not None else archivos
    return archivos, seleccion


def consultar_ollama(config):
    """Comprobación previa sin inferencia ni descarga automática de modelos.

    API: https://docs.ollama.com/api/tags
    Version: https://github.com/ollama/ollama/blob/main/docs/api.md#version
    """
    def consultar(endpoint):
        try:
            with urlopen(config.url_ollama.rstrip("/") + endpoint,
                         timeout=min(config.timeout_segundos, 15)) as respuesta:
                return h.parsear_json(respuesta.read().decode("utf-8"))
        except HTTPError as exc:
            raise ValueError(f"Ollama respondió HTTP {exc.code} en {endpoint}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ValueError("No se puede conectar con Ollama. Abre Ollama y verifica "
                             f"la dirección {config.url_ollama}. Detalle: {exc}") from exc

    catalogo = consultar("/api/tags")
    candidatos = [m for m in catalogo.get("models", [])
                  if config.modelo in (m.get("name"), m.get("model"))]
    if len(candidatos) != 1:
        disponibles = [m.get("name", m.get("model")) for m in catalogo.get("models", [])]
        raise ValueError(f"No se encontró de forma única el modelo {config.modelo!r}. "
                         f"Modelos disponibles: {disponibles}. Usa --modelo con su nombre exacto.")
    informacion = {"modelo": candidatos[0], "consultado_utc": ahora()}
    try:
        informacion["servidor"] = consultar("/api/version")
    except ValueError as exc:
        # La falta de esta metainformación no impide inferencia; queda explícita.
        informacion["advertencia_version"] = str(exc)
    return informacion


def fila_resumen(caso, archivo, resultado):
    eventos = resultado.get("trace", {}).get("eventos", [])
    respuestas = [e["respuesta"] for e in eventos if e.get("tipo") == "respuesta_modelo"]
    salida = resultado.get("salida_7_claves")

    def total_tokens(campo):
        return sum(r[campo] for r in respuestas
                   if type(r.get(campo)) is int and r[campo] >= 0)

    return {
        "caso": caso, "archivo": archivo, "estado": resultado["estado"],
        "segundos": resultado["segundos"],
        "llamadas_iniciadas": sum(e.get("tipo") == "llamada_iniciada" for e in eventos),
        "respuestas_recibidas": len(respuestas),
        "correcciones_aplicadas": sum(e.get("tipo") == "correccion_aplicada" for e in eventos),
        "tokens_entrada_reportados": total_tokens("prompt_eval_count"),
        "tokens_salida_reportados": total_tokens("eval_count"),
        "suministros_confirmados": len(salida["suministros_confirmados"]) if salida else None,
        "suministros_condicionales": len(salida["suministros_condicionales"]) if salida else None,
        "requerimientos_operativos": len(salida["requerimientos_operativos"]) if salida else None,
        "urgencia": salida["urgencia"]["nivel"] if salida else None,
        "vista_4_disponible": resultado.get("salida_4_claves") is not None,
        "pendientes_revision": " | ".join(resultado["pendientes_revision"]),
    }


def guardar_resumen(carpeta, filas, manifiesto):
    temporal = carpeta / "resumen.csv.tmp"
    with temporal.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(filas)
    temporal.replace(carpeta / "resumen.csv")
    conteos = {estado: sum(f["estado"] == estado for f in filas)
               for estado in ("VALIDADA", "PARCIAL", "ERROR", "INTERRUMPIDO")}
    resumen = {
        "seleccionados": len(manifiesto["casos"]), "registrados": len(filas),
        "no_iniciados": sum(caso["estado"] == "PENDIENTE" for caso in manifiesto["casos"]),
        "estados": conteos,
        "segundos_casos_registrados": round(sum(f["segundos"] for f in filas), 3),
        "llamadas_iniciadas": sum(f["llamadas_iniciadas"] for f in filas),
        "nota": "Estos son estados técnicos del sistema, no una medición de exactitud contra respuestas de referencia.",
    }
    c.guardar_json(carpeta / "resumen.json", resumen)
    c.guardar_json(carpeta / "ejecucion.json", manifiesto)


def ejecutar_lote(archivos, config, carpeta_salida, info_ollama, encoding=ENCODING,
                  procesador=None):
    """Devuelve (carpeta_de_ejecucion, codigo_salida).

    procesador permite probar lectura/guardado sin llamar al modelo.
    La comprobación de conexión se realiza en main antes de iniciar este lote.
    """
    procesador = procesador or c.procesar_mensaje
    if not archivos:
        raise ValueError("No se seleccionaron casos.")
    # Leer TODOS los casos antes de inferir; sin decodificaciones silenciosas.
    entradas = []
    for archivo in archivos:
        contenido = archivo.read_bytes()
        try:
            texto = contenido.decode(encoding)
        except UnicodeError as exc:
            raise ValueError(f"No se pudo leer {archivo.name} con {encoding}. "
                             "Guárdalo como UTF-8 o indica --encoding explícitamente.") from exc
        if not texto.strip():
            raise ValueError(f"El caso {archivo.name} está vacío.")
        entradas.append((archivo, contenido, texto))
    fuentes = {}
    for nombre in FUENTES:
        origen = Path(config.carpeta_prompts) / nombre if nombre.endswith(".txt") else BASE / nombre
        fuentes[nombre] = origen.read_bytes()
        if not fuentes[nombre].strip():
            raise ValueError(f"Archivo de sistema vacío: {origen}")

    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    carpeta = Path(carpeta_salida) / f"run_{sello}_{uuid.uuid4().hex[:6]}"
    carpeta.mkdir(parents=True, exist_ok=False)
    for nombre in ("entradas", "fuentes", "resultados", "salidas_7", "salidas_4", "traces"):
        (carpeta / nombre).mkdir()
    for nombre, contenido in fuentes.items():
        (carpeta / "fuentes" / nombre).write_bytes(contenido)
    # Cada caso lee los mismos prompts congelados aunque se editen los originales.
    config_ejecucion = replace(config, carpeta_prompts=str((carpeta / "fuentes").resolve()))
    manifiesto = {
        "inicio_utc": ahora(), "estado_lote": "EN_CURSO",
        "python": sys.version, "plataforma": platform.platform(),
        "configuracion": asdict(config_ejecucion), "ollama": copy.deepcopy(info_ollama),
        "encoding_entradas": encoding,
        "fuentes_sha256": {n: huella(b) for n, b in fuentes.items()}, "casos": [],
        "nota": "Los casos PARCIAL con extracción utilizable generan vistas provisionales de 7 y 4 claves. Revisar estado y pendientes en resultados; los JSON de vistas conservan sus claves originales.",
    }
    for indice, (archivo, contenido, texto) in enumerate(entradas, 1):
        # El prefijo evita colisiones aun si dos casos tienen igual contenido.
        id_caso = f"caso_{indice:03d}_{huella(archivo.name.encode('utf-8'))[:8]}"
        nombre_copia = id_caso + ".txt"
        (carpeta / "entradas" / nombre_copia).write_bytes(contenido)
        manifiesto["casos"].append({"id": id_caso, "archivo_original": archivo.name,
                                  "ruta_original": str(archivo.resolve()),
                                  "copia": f"entradas/{nombre_copia}", "sha256": huella(contenido),
                                  "estado": "PENDIENTE"})
    filas = []
    guardar_resumen(carpeta, filas, manifiesto)
    print(f"\nEjecución: {carpeta.resolve()}", flush=True)
    print("Los estados VALIDADA/PARCIAL/ERROR no equivalen a exactitud del modelo.\n", flush=True)
    interrumpido = False
    inicio_lote = time.perf_counter()
    try:
        for (archivo, contenido, texto), caso in zip(entradas, manifiesto["casos"]):
            id_caso = caso["id"]
            ruta_trace = carpeta / "traces" / f"{id_caso}.json"
            caso["estado"] = "EN_CURSO"
            guardar_resumen(carpeta, filas, manifiesto)
            print(f"[{len(filas)+1}/{len(entradas)}] {archivo.name} ...", flush=True)
            inicio = time.perf_counter()
            try:
                resultado = procesador(texto, id_mensaje=id_caso, config=config_ejecucion,
                                       ruta_trace=ruta_trace)
            except OSError:
                # Un fallo de guardado no se disfraza de error de extracción.
                raise
            except (Exception, KeyboardInterrupt) as exc:
                interrumpido = isinstance(exc, KeyboardInterrupt)
                estado = "INTERRUMPIDO" if interrumpido else "ERROR"
                detalle = "Interrupción solicitada con Ctrl+C." if interrumpido else traceback.format_exc()
                trace = h.parsear_json(ruta_trace.read_text(encoding="utf-8")) if ruta_trace.exists() else {
                    "id_mensaje": id_caso, "mensaje_original": texto, "eventos": []}
                trace.setdefault("eventos", []).append({"tipo": "error_ejecutor", "fecha_utc": ahora(), "error": detalle})
                trace["estado_ejecutor"] = estado
                c.guardar_json(ruta_trace, trace)
                resultado = {"id_mensaje": id_caso, "estado": estado, "salida_7_claves": None,
                             "salida_4_claves": None, "pendientes_revision": [detalle],
                             "segundos": round(time.perf_counter() - inicio, 3), "trace": trace}
            # Mantener siempre un registro por caso, incluso si no hay JSON final.
            sin_trace = {k: v for k, v in resultado.items() if k != "trace"}
            c.guardar_json(carpeta / "resultados" / f"{id_caso}.json", sin_trace)
            for cantidad in (7, 4):
                salida = resultado.get(f"salida_{cantidad}_claves")
                if salida is not None:
                    c.guardar_json(carpeta / f"salidas_{cantidad}" / f"{id_caso}_{resultado['estado']}.json", salida)
            caso["estado"] = resultado["estado"]
            filas.append(fila_resumen(id_caso, archivo.name, resultado))
            guardar_resumen(carpeta, filas, manifiesto)
            print(f"  {resultado['estado']} | {resultado['segundos']:.1f} s | "
                  f"{filas[-1]['llamadas_iniciadas']} llamadas", flush=True)
            if interrumpido:
                break
    except BaseException as exc:
        manifiesto["estado_lote"] = "ABORTADA"
        manifiesto["error_ejecutor"] = f"{type(exc).__name__}: {exc}"
        manifiesto["fin_utc"] = ahora()
        guardar_resumen(carpeta, filas, manifiesto)
        raise
    manifiesto["estado_lote"] = "INTERRUMPIDA" if interrumpido else "COMPLETADA"
    manifiesto["fin_utc"] = ahora()
    manifiesto["segundos_lote"] = round(time.perf_counter() - inicio_lote, 3)
    guardar_resumen(carpeta, filas, manifiesto)
    # Posprocesado independiente: las llamadas y decisiones de los agentes
    # ya terminaron. El coordinador no importa ni ejecuta este exportador.
    exportar_traces_legibles(carpeta)
    print(f"\nResultados y resumen: {carpeta.resolve()}", flush=True)
    codigo = 130 if interrumpido else (0 if all(f["estado"] == "VALIDADA" for f in filas) else 2)
    return carpeta, codigo


def exportar_traces_legibles(carpeta):
    """Leer los JSON terminados, sin cambiar resultados ni llamar al modelo."""
    from traces_legibles import guardar_trace_legible
    carpeta = Path(carpeta)
    try:
        (carpeta / "traces_v1").mkdir(exist_ok=True)
    except OSError as exc:
        aviso = f"No se pudo crear traces_v1: {exc}"
        print(aviso, file=sys.stderr)
        return [aviso]
    errores = []
    for archivo in sorted((carpeta / "traces").glob("*.json")):
        try:
            trace = json.loads(archivo.read_text(encoding="utf-8-sig"))
            guardar_trace_legible(trace, archivo)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errores.append(f"{archivo.name}: {exc}")
    if errores:
        print("\nAviso: algunos trazos legibles no pudieron generarse. "
              "Los resultados y traces originales se conservan.", file=sys.stderr)
        for error in errores:
            print("  " + error, file=sys.stderr)
    return errores


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ejecutar los casos TXT con los tres agentes.")
    parser.add_argument("--entradas", default="Prompts_separados")
    parser.add_argument("--salidas", default="Outputs_D3")
    parser.add_argument("--esperados", type=int, default=21, help="Número esperado de TXT; 0 desactiva el control")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--limite", type=int, help="Ejecutar solo los primeros N casos")
    grupo.add_argument("--caso", help="Nombre exacto de un TXT, incluida su extensión")
    parser.add_argument("--listar", action="store_true", help="Listar selección sin llamar a Ollama ni crear resultados")
    parser.add_argument("--encoding", default=ENCODING)
    parser.add_argument("--modelo")
    parser.add_argument("--url-ollama")
    parser.add_argument("--num-ctx", type=int)
    parser.add_argument("--num-predict", type=int)
    parser.add_argument("--timeout", type=float, dest="timeout_segundos")
    parser.add_argument("--rondas-correccion", type=int)
    parser.add_argument("--think", choices=("false", "true", "auto"), help="auto omite el parámetro think")
    args = parser.parse_args(argv)
    try:
        if args.esperados < 0:
            raise ValueError("--esperados no puede ser negativo.")
        encontrados, seleccion = descubrir_casos(ruta_desde_script(args.entradas),
                                                args.esperados, args.limite, args.caso)
        print(f"TXT encontrados: {len(encontrados)}. Seleccionados: {len(seleccion)}.", flush=True)
        if args.listar:
            for i, archivo in enumerate(seleccion, 1):
                print(f"{i:02d}. {archivo.name}")
            return 0
        cambios = {k: getattr(args, k) for k in ("modelo", "url_ollama", "num_ctx", "num_predict",
                   "timeout_segundos", "rondas_correccion") if getattr(args, k) is not None}
        if args.think is not None:
            cambios["pensar"] = {"false": False, "true": True, "auto": None}[args.think]
        config = c.Configuracion(**cambios)
        info = consultar_ollama(config)
        _, codigo = ejecutar_lote(seleccion, config, ruta_desde_script(args.salidas), info, args.encoding)
        return codigo
    except KeyboardInterrupt:
        print("\nEjecución interrumpida.", file=sys.stderr)
        return 130
    except (ValueError, OSError, LookupError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
