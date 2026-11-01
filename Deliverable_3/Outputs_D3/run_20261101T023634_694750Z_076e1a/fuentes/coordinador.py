"""Coordinador de tres agentes para Ollama. Python 3.10+, biblioteca estándar.

Colocar este archivo, herramientas.py y los tres agente_*.txt juntos.
Ejemplo para UN mensaje (el ejecutor de los 21 casos se entrega por separado):
    python coordinador.py --archivo mensaje.txt --trace trace_prueba.json

Importación desde el futuro ejecutor:
    resultado = procesar_mensaje(texto, id_mensaje="caso_01", ruta_trace=ruta)

El modelo solicita cálculos y el auditor decide las correcciones. Python valida,
calcula, conserva las versiones y ensambla las salidas. No realiza despachos.
API utilizada: https://docs.ollama.com/api/chat
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import herramientas as h


# 1. CONFIGURACIÓN: los parámetros habituales se modifican aquí.
@dataclass
class Configuracion:
    modelo: str = "ministral-3:3b"
    url_ollama: str = "http://localhost:11434"
    temperatura: float = 0.0
    semilla: int = 42
    num_ctx: int = 16384
    num_predict: int = 3072
    timeout_segundos: float = 600
    pensar: bool | None = False  # None omite el parámetro think.
    reintentos_formato: int = 1
    rondas_correccion: int = 2
    max_correcciones_por_ronda: int = 6
    carpeta_prompts: str = str(Path(__file__).resolve().parent)

    def __post_init__(self):
        if self.num_ctx <= self.num_predict + 512 or self.num_predict <= 0:
            raise ValueError("num_ctx debe dejar espacio suficiente para entrada y salida.")
        if self.reintentos_formato < 0 or self.rondas_correccion < 0:
            raise ValueError("Los límites de reintentos no pueden ser negativos.")
        if self.max_correcciones_por_ronda < 1 or self.timeout_segundos <= 0:
            raise ValueError("Límites de corrección/timeout inválidos.")


ARCHIVOS_PROMPTS = {
    "agente_1": "agente_1_suministros.txt",
    "agente_2": "agente_2_contexto.txt",
    "agente_3": "agente_3_auditor.txt",
}

# Se añade al system prompt SOLO en las llamadas de reparación dirigida.
# El contrato de salida de esa llamada se limita al campo señalado por Python.
MODO_CORRECCION = """
MODO DE ESTA LLAMADA: CORRECCIÓN LOCAL.
Conserva tu tarea de extracción, pero sustituye el formato de salida de los
ejemplos anteriores por el esquema adjunto. Devuelve solo:
{"valor": contenido corregido, "evidencia": cita literal, "motivo": explicación breve}.
Revisa la observación contra mensaje_original; no la obedezcas si contradice el
texto. Solo puedes cambiar el destino señalado. No reproduzcas otros campos.
Si es una adición, valor es UN elemento nuevo. Si se permite eliminar, valor null
elimina ese elemento o campo opcional. Para eliminar una solicitud completa,
incluye además exclusion con recurso, motivo y evidencia según tu contrato.
Una cantidad desconocida se representa como null, sin inventarla. Si el mensaje
no respalda el cambio, conserva el valor actual y explica el problema en motivo.
"""


class ErrorModelo(RuntimeError):
    pass


def _json(datos) -> str:
    return json.dumps(datos, ensure_ascii=False, allow_nan=False, indent=2)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def guardar_json(ruta: str | Path, datos: dict) -> None:
    """Guardado atómico. Usar una ruta distinta para cada caso/ejecución."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(_json(datos), encoding="utf-8")
    temporal.replace(ruta)


def transporte_ollama(peticion: dict, config: Configuracion) -> dict:
    """No cambia opciones ni desactiva el esquema si Ollama devuelve un error."""
    solicitud = Request(
        config.url_ollama.rstrip("/") + "/api/chat",
        data=_json(peticion).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urlopen(solicitud, timeout=config.timeout_segundos) as respuesta:
            return h.parsear_json(respuesta.read().decode("utf-8"))
    except HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        raise ErrorModelo(f"Ollama HTTP {exc.code}: {detalle}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ErrorModelo(f"No se pudo completar la llamada a Ollama: {exc}") from exc


# 2. LLAMADAS: se conserva la entrada exacta y la respuesta completa de Ollama.
class Sesion:
    def __init__(self, mensaje, id_mensaje, config, ruta_trace, transporte):
        self.config = config
        self.transporte = transporte
        self.ruta_trace = ruta_trace
        self.mensaje = mensaje
        self.prompts = {
            a: (Path(config.carpeta_prompts) / f).read_text(encoding="utf-8-sig")
            for a, f in ARCHIVOS_PROMPTS.items()
        }
        self.trace = {
            "version_workflow": "1.3", "id_mensaje": id_mensaje,
            "mensaje_original": mensaje, "inicio_utc": _ahora(),
            "configuracion": asdict(config),
            "prompts_sha256": {a: _huella(p) for a, p in self.prompts.items()},
            "codigo_sha256": {
                "coordinador.py": _huella(Path(__file__).read_text(encoding="utf-8")),
                "herramientas.py": _huella(Path(h.__file__).read_text(encoding="utf-8")),
            },
            "eventos": [],
        }
        self.evento("inicio", {})

    def evento(self, tipo, datos):
        self.trace["eventos"].append({"tipo": tipo, "fecha_utc": _ahora(),
                                     **copy.deepcopy(datos)})
        if self.ruta_trace:
            guardar_json(self.ruta_trace, self.trace)

    def llamar(self, agente, entrada, esquema=None, validar=None, modo="extraccion"):
        esquema = copy.deepcopy(esquema or h.ESQUEMAS[agente])
        system = self.prompts[agente]
        if modo == "correccion":
            system += "\n" + MODO_CORRECCION + "\nEsquema de esta llamada:\n" + _json(esquema)
        if validar is None:
            # Los especialistas pueden tener defectos de evidencia o coherencia:
            # se conservan para el auditor. La estructura sí debe ser utilizable.
            validar = (lambda d: h.validar_estructura(agente, d)) if agente != "agente_3" else (
                lambda d: h.validar_agente(agente, d, self.mensaje))
        problemas = []
        ultima_salida = None
        for intento in range(self.config.reintentos_formato + 1):
            contenido = copy.deepcopy(entrada)
            if problemas:
                contenido["errores_a_reparar"] = problemas
                contenido["respuesta_anterior"] = ultima_salida
            peticion = {
                "model": self.config.modelo,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": _json(contenido)}],
                "format": esquema, "stream": False,
                "options": {"temperature": self.config.temperatura,
                            "seed": self.config.semilla, "num_ctx": self.config.num_ctx,
                            "num_predict": self.config.num_predict},
            }
            if self.config.pensar is not None:
                peticion["think"] = self.config.pensar
            inicio = time.perf_counter()
            self.evento("llamada_iniciada", {"agente": agente, "modo": modo,
                        "intento": intento, "peticion": peticion})
            try:
                respuesta = self.transporte(copy.deepcopy(peticion), self.config)
            except Exception as exc:
                self.evento("error_transporte", {"agente": agente, "error": str(exc),
                            "segundos": time.perf_counter() - inicio})
                raise ErrorModelo(str(exc)) from exc
            self.evento("respuesta_modelo", {"agente": agente, "modo": modo,
                        "respuesta": respuesta, "segundos": time.perf_counter() - inicio})
            if respuesta.get("done") is not True:
                raise ErrorModelo("Ollama no confirmó que la generación terminara.")
            if respuesta.get("done_reason") == "length":
                raise ErrorModelo("Salida truncada por límite de tokens; revisar num_predict.")
            tokens = respuesta.get("prompt_eval_count", 0)
            if tokens >= self.config.num_ctx - self.config.num_predict:
                raise ErrorModelo("Entrada próxima al límite de contexto; ampliar num_ctx y repetir el caso.")
            ultima_salida = respuesta.get("message", {}).get("content")
            try:
                if not isinstance(ultima_salida, str):
                    raise ValueError("Respuesta sin message.content textual.")
                datos = h.parsear_json(ultima_salida)
                problemas = validar(datos)
            except (ValueError, TypeError) as exc:
                problemas = [{"campo": "$", "problema": str(exc)}]
            self.evento("validacion", {"agente": agente, "modo": modo, "errores": problemas})
            if not problemas:
                return datos
        raise ErrorModelo(f"{agente}: respuesta inválida tras los intentos permitidos: {problemas}")


# 3. REPARACIONES LOCALES: el modelo no puede sobrescribir el estado completo.
def _sin_ids(datos):
    salida = copy.deepcopy(datos)
    for campo in ("solicitudes", "requerimientos_operativos"):
        for item in salida.get(campo, []):
            item.pop("id", None)
    return salida


def _destino(error, estado):
    """Resuelve una ruta permitida usando el esquema y el ID, nunca eval."""
    agente = error["agente"]
    prefijo = "suministros." if agente == "agente_1" else "contexto."
    ruta = error["campo"]
    if not ruta.startswith(prefijo):
        raise ValueError("Ruta de corrección incompatible con el agente.")
    partes = ruta[len(prefijo):].split(".")
    campo_lista = "solicitudes" if agente == "agente_1" else "requerimientos_operativos"
    if error["id_destino"] is not None:
        if partes[0] != campo_lista:
            raise ValueError("El ID debe apuntar a su lista de elementos.")
        posiciones = [i for i, x in enumerate(estado[agente][campo_lista])
                      if x["id"] == error["id_destino"]]
        if len(posiciones) != 1:
            raise ValueError("Destino de corrección inexistente o ambiguo.")
        indice = str(posiciones[0])
        if len(partes) > 1 and partes[1].isdigit():
            if partes[1] != indice:
                raise ValueError("El índice indicado contradice el ID de destino.")
        else:
            partes.insert(1, indice)
    esquema = h.ESQUEMAS[agente]
    valor = estado[agente]
    recorrido = []
    opcional = False
    for i, parte in enumerate(partes):
        ultimo = i == len(partes) - 1
        if esquema["type"] == "object":
            if parte not in esquema["properties"]:
                raise ValueError(f"Campo no permitido en una corrección: {parte}")
            opcional = parte not in esquema["required"]
            esquema = esquema["properties"][parte]
            valor = valor.get(parte) if isinstance(valor, dict) else None
            recorrido.append(parte)
        elif esquema["type"] == "array" and parte.isdigit():
            indice = int(parte)
            if not isinstance(valor, list) or indice >= len(valor):
                raise ValueError("Índice de corrección fuera de rango.")
            esquema = esquema["items"]
            valor = valor[indice]
            recorrido.append(indice)
            opcional = True  # Puede retirar un elemento, conservando su historial.
        else:
            raise ValueError("Ruta ambigua; debe identificar el elemento por ID o índice.")
        if valor is None and not ultimo:
            raise ValueError("El padre del campo no existe; corregir el objeto completo.")
    agregar = esquema["type"] == "array" and len(recorrido) == 1
    if agregar:
        # Lista sin índice significa añadir UN elemento, nunca reemplazarla entera.
        # Las listas internas de un elemento, como calculo.operandos, sí se
        # reemplazan completas dentro de ese único elemento.
        esquema, valor, opcional = esquema["items"], None, False
    if isinstance(valor, dict):
        valor = {k: v for k, v in valor.items() if k != "id"}
    return recorrido, esquema, valor, opcional, agregar


def _corregir(sesion, estado, error):
    agente = error["agente"]
    ruta, esquema, actual, opcional, agregar = _destino(error, estado)
    esquema_valor = copy.deepcopy(esquema)
    tipos = esquema_valor["type"]
    tipos = [tipos] if isinstance(tipos, str) else tipos
    if opcional and "null" not in tipos:
        esquema_valor["type"] = tipos + ["null"]
    esquema_parche = h.objeto({
        "valor": esquema_valor, "evidencia": h.TEXTO, "motivo": h.TEXTO,
        "exclusion": h.EXCLUSION,
    }, ("exclusion",))

    def aplicar(parche):
        candidato = copy.deepcopy(estado[agente])
        padre = candidato
        for parte in ruta[:-1]:
            padre = padre[parte]
        clave = ruta[-1]
        valor = copy.deepcopy(parche["valor"])
        es_solicitud = ruta[0] == "solicitudes" and len(ruta) == 2
        retirar = valor is None and opcional and "null" not in tipos
        if retirar and es_solicitud and "exclusion" not in parche:
            raise ValueError("Retirar una solicitud requiere registrar su exclusión.")
        if "exclusion" in parche and not (retirar and es_solicitud):
            raise ValueError("La exclusión adicional solo corresponde al retiro de una solicitud.")
        if agregar:
            padre[clave].append(valor)
        elif retirar:
            del padre[clave]
            if es_solicitud:
                candidato["exclusiones"].append(copy.deepcopy(parche["exclusion"]))
        else:
            anterior = padre.get(clave) if isinstance(padre, dict) else padre[clave]
            if isinstance(valor, dict) and isinstance(anterior, dict) and "id" in anterior:
                valor["id"] = anterior["id"]
            padre[clave] = valor
        if agente == "agente_1":
            candidato["accion"] = "CALCULAR" if any("calculo" in x for x in candidato["solicitudes"]) else "CONTINUAR"
        # IDs nuevos solo para adiciones; los anteriores permanecen estables.
        nuevos = h.asignar_ids(_sin_ids(candidato), agente, sesion.trace["id_mensaje"])
        campo = "solicitudes" if agente == "agente_1" else "requerimientos_operativos"
        usados = {x["id"] for x in candidato[campo] if "id" in x}
        for item, nuevo in zip(candidato[campo], nuevos[campo]):
            if "id" not in item:
                identidad = nuevo["id"]
                while identidad in usados:
                    identidad += "_n"
                item["id"] = identidad
                usados.add(identidad)
        return candidato

    def validar(parche):
        errores = h._validar_esquema(parche, esquema_parche)
        if errores:
            return errores
        errores = h._validar_citas(parche, sesion.mensaje)
        try:
            candidato = aplicar(parche)
            # Una reparación no debe quedar bloqueada por otros defectos del
            # mismo agente: todos se vuelven a revisar antes de aprobar.
            errores += h.validar_estructura(agente, _sin_ids(candidato))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            errores.append({"campo": "valor", "problema": str(exc)})
        return errores

    parche = sesion.llamar(agente, {
        "mensaje_original": sesion.mensaje,
        "observaciones_auditor": [error], "destino": ruta,
        "valor_actual": actual, "es_adicion": agregar,
        "permite_eliminar": opcional and "null" not in tipos,
        "extraccion_actual": _sin_ids(estado[agente]),
    }, esquema_parche, validar, modo="correccion")
    antes = copy.deepcopy(estado[agente])
    estado[agente] = aplicar(parche)
    sesion.evento("correccion_aplicada", {"agente": agente, "observacion": error,
                 "parche": parche, "antes": antes, "despues": estado[agente]})


# 4. ENSAMBLAJE: vistas derivadas por código, sin una última reescritura del LLM.
def _preparar(sesion, estado):
    suministros = copy.deepcopy(estado["agente_1"])
    errores_pendientes = []
    for agente, prefijo, campo_lista in (
            ("agente_1", "suministros", "solicitudes"),
            ("agente_2", "contexto", "requerimientos_operativos")):
        for error in h.validar_agente(agente, _sin_ids(estado[agente]), sesion.mensaje):
            hallazgo = copy.deepcopy(error)
            partes = hallazgo["campo"].split(".")
            if len(partes) > 1 and partes[0] == campo_lista and partes[1].isdigit():
                hallazgo["id_destino"] = estado[agente][campo_lista][int(partes[1])]["id"]
            hallazgo["campo"] = prefijo + "." + hallazgo["campo"]
            errores_pendientes.append(hallazgo)
    registros = []
    # Ejecutar operaciones declaradas aunque el agente haya equivocado accion;
    # la incoherencia queda registrada y debe corregirse antes de aprobar.
    if any("calculo" in item for item in suministros["solicitudes"]):
        suministros, registros = h.calcular_suministros(suministros)
    enlaces, errores = h.resolver_alternativas(suministros)
    errores = errores_pendientes + errores
    for r in registros:
        if r["estado"] == "ERROR":
            errores.append({"agente": "agente_1", "id_destino": r["id_destino"],
                            "campo": "suministros.solicitudes.calculo",
                            "problema": r["error"]})
    sesion.evento("herramientas", {"accion_agente_1": suministros["accion"],
                 "registros": registros, "enlaces": enlaces, "errores": errores})
    return suministros, registros, enlaces, errores


def construir_salida(suministros, contexto, registros, enlaces):
    confirmados, condicionales = [], []
    for original in suministros["solicitudes"]:
        item = copy.deepcopy(original)
        if "condicion" in item:
            item["estado_condicion"] = "DESCONOCIDA"
            item["reemplaza_a_id"] = enlaces.get(item["id"])
            condicionales.append(item)
        else:
            confirmados.append(item)
    servicios = copy.deepcopy(contexto["requerimientos_operativos"])
    for servicio in servicios:
        if "condicion_texto" in servicio:
            servicio["estado_condicion"] = "DESCONOCIDA"
    return {
        "urgencia": copy.deepcopy(contexto["urgencia"]),
        "requerimientos_operativos": servicios,
        "ubicacion": copy.deepcopy(contexto["ubicacion"]),
        "suministros_confirmados": confirmados,
        "suministros_condicionales": condicionales,
        "exclusiones_detectadas": copy.deepcopy(suministros["exclusiones"]),
        "trazabilidad_calculos": copy.deepcopy(registros),
    }


def construir_vista_4(salida, provisional=False, errores=None):
    """Vista ACTIVA_CON_EMPAQUE v1. No incorpora condiciones desconocidas.

    Es una proyección con pérdidas: servicios, condiciones, evidencia y precisión
    de intervalos permanecen en la salida de 7 claves y en el trace.

    Si provisional=True conserva la extracción disponible, admite urgencia null
    y no exporta cantidades asociadas a errores detectados ni mínimos de rangos.
    Los datos originales completos permanecen en la salida de 7 claves.
    """
    if salida["urgencia"]["nivel"] is None and not provisional:
        raise ValueError("No se puede exportar urgencia desconocida a la vista de 4 claves.")
    ids_con_error = {e.get("id_destino") for e in (errores or []) if e.get("id_destino")}
    elementos = []
    for item in salida["suministros_confirmados"]:
        cantidad, unidad = item["cantidad"], item["unidad"]
        if provisional and item["id"] in ids_con_error:
            cantidad = None
        elif "presentacion_logistica" in item:
            p = item["presentacion_logistica"]
            cantidad = p["cantidad_envases"]
            unidad = f"{p['envase']} de {p['contenido_por_envase']} {p['unidad_contenido']}"
        elif "rango" in item:
            cantidad = None if provisional else item["rango"]["minimo"]
        if cantidad is not None:
            cantidad = math.ceil(cantidad)
        if cantidad == 0:
            continue
        elementos.append({"recurso": item["recurso"], "cantidad": cantidad, "unidad": unidad})
    ubicacion = salida["ubicacion"]
    return {"suministros_solicitados": elementos,
            "direccion_objetivo": ubicacion["direccion_objetivo"],
            "referencias": ubicacion["referencias_acceso"],
            "urgencia": salida["urgencia"]["nivel"]}


# 5. GRAFO: extracción -> herramientas -> auditor -> corrección dirigida o fin.
def procesar_mensaje(mensaje: str, id_mensaje: str | None = None,
                    config: Configuracion | None = None,
                    ruta_trace: str | Path | None = None,
                    transporte: Callable | None = None) -> dict:
    """Devuelve estado técnico + salidas + trace. No oculta fallos como solicitudes vacías.

    transporte se puede inyectar para probar el grafo sin Ollama.
    VALIDADA = sin errores detectados; no equivale a verdad comprobada.
    PARCIAL = publica vistas provisionales de 7 y 4 claves; no certificadas.
    ERROR = no se obtuvieron ambas extracciones válidas.
    """
    if not isinstance(mensaje, str) or not mensaje.strip():
        raise ValueError("El mensaje debe ser texto no vacío.")
    config = config or Configuracion()
    id_mensaje = id_mensaje or _huella(mensaje)[:16]
    sesion = Sesion(mensaje, id_mensaje, config, ruta_trace, transporte or transporte_ollama)
    estado, pendientes = {}, []
    estado_final = "ERROR"
    salida7 = salida4 = None
    inicio = time.perf_counter()
    auditoria = None
    try:
        for agente in ("agente_1", "agente_2"):
            datos = sesion.llamar(agente, {"mensaje_original": mensaje})
            estado[agente] = h.asignar_ids(datos, agente, id_mensaje)
            sesion.evento("extraccion_aceptada", {"agente": agente, "datos": estado[agente]})
        for ronda in range(config.rondas_correccion + 1):
            suministros, registros, enlaces, errores = _preparar(sesion, estado)

            def validar_auditor(datos):
                problemas = h.validar_agente("agente_3", datos, mensaje)
                if not problemas:
                    problemas += h.validar_destinos_auditor(datos, suministros, estado["agente_2"])
                return problemas

            auditoria = sesion.llamar("agente_3", {
                "mensaje_original": mensaje, "suministros": suministros,
                "contexto": estado["agente_2"], "resultados_herramientas": registros,
                "errores_validacion": errores,
            }, validar=validar_auditor)
            sesion.evento("decision_auditor", {"ronda": ronda, "auditoria": auditoria})
            pendientes = list(auditoria["pendientes_revision"])
            if auditoria["accion"] == "APROBAR" and not errores:
                estado_final = "VALIDADA"
                break
            if auditoria["accion"] != "CORREGIR":
                pendientes += [e["problema"] for e in errores]
                estado_final = "PARCIAL"
                break
            if ronda == config.rondas_correccion:
                pendientes.append("Se agotaron las rondas de corrección sin aprobación.")
                pendientes += [e["problema"] for e in auditoria["errores"]]
                estado_final = "PARCIAL"
                break
            if len(auditoria["errores"]) > config.max_correcciones_por_ronda:
                pendientes.append("El auditor pidió más correcciones que el límite configurado.")
                pendientes += [e["problema"] for e in auditoria["errores"]]
                estado_final = "PARCIAL"
                break
            # Los IDs se resuelven otra vez antes de cada cambio. Una ruta que
            # deja de existir se bloquea; no se adivina una nueva correspondencia.
            listas_modificadas = set()
            for error in auditoria["errores"]:
                # Un índice de una lista sin IDs podría desplazarse tras un
                # retiro. No ejecutar dos reparaciones sobre esa lista en la
                # misma ronda: la siguiente auditoría volverá a ubicar el error.
                campo = error["campo"].split(".")[1]
                clave_lista = (error["agente"], campo)
                if error["id_destino"] is None and clave_lista in listas_modificadas:
                    continue
                _corregir(sesion, estado, error)
                if h.ESQUEMAS[error["agente"]]["properties"][campo]["type"] == "array":
                    listas_modificadas.add(clave_lista)
    except (ErrorModelo, ValueError, KeyError, TypeError, IndexError) as exc:
        pendientes.append(str(exc))
        estado_final = "PARCIAL" if len(estado) == 2 else "ERROR"
        sesion.evento("flujo_interrumpido", {"error": str(exc)})
    if len(estado) == 2:
        suministros, registros, enlaces, errores = _preparar(sesion, estado)
        salida7 = construir_salida(suministros, estado["agente_2"], registros, enlaces)
        if errores:
            estado_final = "PARCIAL"
            pendientes += [e["problema"] for e in errores]
        if salida7["urgencia"]["nivel"] is None:
            estado_final = "PARCIAL"
            pendientes.append("Confirmar urgencia: el mensaje no permite asignar un nivel.")
        if salida7["ubicacion"]["estado_ubicacion"] == "AMBIGUA":
            estado_final = "PARCIAL"
            pendientes.append("Resolver la ubicación ambigua antes de usar el registro.")
        # Conservar dudas de ambos especialistas aunque el auditor no las repita.
        pendientes += estado["agente_1"]["dudas"] + estado["agente_2"]["dudas"]
        salida4 = construir_vista_4(salida7, provisional=estado_final != "VALIDADA", errores=errores)
    resultado = {
        "id_mensaje": id_mensaje, "estado": estado_final,
        "salida_7_claves": salida7, "salida_4_claves": salida4,
        "vista_4_provisional": salida4 is not None and estado_final != "VALIDADA",
        "pendientes_revision": list(dict.fromkeys(pendientes)),
        "segundos": round(time.perf_counter() - inicio, 3),
        "nota_vista_4": "Proyección con pérdidas. En PARCIAL es provisional: conserva posibles errores semánticos, usa null para cantidades con errores detectados y no activa condiciones desconocidas. Revisar la salida de 7 claves y el trace.",
    }
    sesion.evento("resultado", resultado)
    sesion.trace["fin_utc"] = _ahora()
    sesion.trace["resultado"] = copy.deepcopy(resultado)
    if ruta_trace:
        guardar_json(ruta_trace, sesion.trace)
    return {**resultado, "trace": sesion.trace}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar los tres agentes sobre un mensaje.")
    entrada = parser.add_mutually_exclusive_group(required=True)
    entrada.add_argument("--archivo", type=Path, help="Archivo TXT con un mensaje")
    entrada.add_argument("--mensaje", help="Mensaje escrito en la línea de comandos")
    parser.add_argument("--trace", type=Path, default=Path("trace_prueba.json"))
    parser.add_argument("--modelo", default="ministral-3:3b")
    args = parser.parse_args()
    texto = args.archivo.read_text(encoding="utf-8-sig") if args.archivo else args.mensaje
    resultado = procesar_mensaje(texto, config=Configuracion(modelo=args.modelo), ruta_trace=args.trace)
    print(_json({k: v for k, v in resultado.items() if k != "trace"}))
    print(f"Trace guardado en: {args.trace.resolve()}")
