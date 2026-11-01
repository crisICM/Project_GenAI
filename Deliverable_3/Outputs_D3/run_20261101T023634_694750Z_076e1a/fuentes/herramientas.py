"""Herramientas deterministas para Deliverable 3. Python 3.10+, sin dependencias.

No llama a Ollama. El coordinador usará este orden:
  parsear_json -> validar_agente -> asignar_ids -> calcular_suministros
  -> resolver_alternativas -> auditor.

Las funciones trabajan sobre copias: el coordinador debe guardar también cada
respuesta original. Los errores se devuelven explícitamente o lanzan ValueError.
Una validación correcta no garantiza que la interpretación del texto sea correcta.
Los esquemas ESQUEMAS también podrán enviarse a Ollama como formato de respuesta.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from decimal import Decimal, localcontext
from typing import Any


# 1. CONTRATOS DE LOS TRES PROMPTS
# Los campos opcionales se omiten; los desconocidos admitidos usan null.
TEXTO = {"type": "string", "minLength": 1}
TEXTO_NULO = {"type": ["string", "null"], "minLength": 1}
NUMERO = {"type": "number", "minimum": 0}
NUMERO_NULO = {"type": ["number", "null"], "minimum": 0}


def opciones(*valores: str) -> dict:
    return {"type": "string", "enum": list(valores)}


def lista(elemento: dict) -> dict:
    return {"type": "array", "items": elemento}


def objeto(campos: dict, opcionales: tuple = ()) -> dict:
    return {"type": "object", "properties": campos,
            "required": [c for c in campos if c not in opcionales],
            "additionalProperties": False}


CALCULO = objeto({
    "tipo": opciones("DIFERENCIA", "PRODUCTO"),
    "operandos": {**lista(NUMERO), "minItems": 2, "maxItems": 16},
    "unidad_resultado": TEXTO_NULO, "evidencia": TEXTO,
})
PRESENTACION = objeto({
    "cantidad_envases": {"type": "integer", "minimum": 1},
    "envase": TEXTO,
    "contenido_por_envase": {"type": "number", "exclusiveMinimum": 0},
    "unidad_contenido": TEXTO,
})
CONDICION = objeto({
    "texto": TEXTO, "efecto": opciones("AGREGAR", "ALTERNATIVA"),
    "reemplaza_evidencia": TEXTO_NULO,
})
SOLICITUD = objeto({
    "recurso": TEXTO, "cantidad": NUMERO_NULO, "unidad": TEXTO_NULO,
    "evidencia": TEXTO,
    "rango": objeto({"minimo": NUMERO, "maximo": NUMERO}),
    "presentacion_logistica": PRESENTACION,
    "calculo": CALCULO, "condicion": CONDICION,
}, ("rango", "presentacion_logistica", "calculo", "condicion"))
EXCLUSION = objeto({
    "recurso": TEXTO,
    "motivo": opciones("DONACION_OFRECIDA", "YA_RECIBIDO", "NO_REQUERIDO",
                       "CANCELADO", "CORRECCION_DESCARTADA", "HISTORICO",
                       "FUERA_DE_AMBITO"),
    "evidencia": TEXTO,
})
SERVICIO = objeto({
    "tipo": TEXTO, "descripcion": TEXTO,
    "origen": opciones("SOLICITADO", "REQUIERE_EVALUACION"),
    "evidencia": TEXTO, "condicion_texto": TEXTO,
}, ("condicion_texto",))
UBICACION = objeto({
    "direccion_objetivo": TEXTO_NULO, "referencias_acceso": TEXTO_NULO,
    "localidad_detectada": TEXTO_NULO, "estado_ruta": TEXTO_NULO,
    "estado_ubicacion": opciones("IDENTIFICADA", "PARCIAL", "AMBIGUA", "NO_INFORMADA"),
})
URGENCIA = objeto({
    "nivel": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
    "motivo_principal": TEXTO_NULO,
    "requiere_rescate_humano": {"type": ["boolean", "null"]},
})
ERROR_AUDITOR = objeto({
    "agente": opciones("agente_1", "agente_2"), "id_destino": TEXTO_NULO,
    "campo": TEXTO, "problema": TEXTO, "evidencia": TEXTO_NULO,
    "instruccion": TEXTO,
}, ("evidencia",))
ESQUEMAS = {
    "agente_1": objeto({
        "accion": opciones("CALCULAR", "CONTINUAR"),
        "solicitudes": lista(SOLICITUD), "exclusiones": lista(EXCLUSION),
        "dudas": lista(TEXTO),
    }),
    "agente_2": objeto({
        "accion": opciones("AUDITAR"), "ubicacion": UBICACION,
        "requerimientos_operativos": lista(SERVICIO), "urgencia": URGENCIA,
        "evidencias": lista(objeto({"campo": TEXTO, "cita": TEXTO})),
        "dudas": lista(TEXTO),
    }),
    "agente_3": objeto({
        "accion": opciones("APROBAR", "CORREGIR", "REVISION_MANUAL"),
        "errores": lista(ERROR_AUDITOR), "pendientes_revision": lista(TEXTO),
    }),
}


# 2. LECTURA ESTRICTA: nunca reemplazar una respuesta inválida por {}.
def parsear_json(texto: str) -> dict:
    def pares_unicos(pares):
        resultado = {}
        for clave, valor in pares:
            if clave in resultado:
                raise ValueError(f"Clave JSON repetida: {clave}")
            resultado[clave] = valor
        return resultado

    def rechazar_constante(valor):
        raise ValueError(f"Número JSON no permitido: {valor}")

    datos = json.loads(texto, object_pairs_hook=pares_unicos,
                       parse_constant=rechazar_constante)
    if not isinstance(datos, dict):
        raise ValueError("La respuesta debe ser un objeto JSON.")
    return datos


def _numero(valor: Any) -> bool:
    # bool es subclase de int en Python, pero no es una cantidad.
    return type(valor) in (int, float) and (
        type(valor) is int or math.isfinite(valor))


def _validar_esquema(valor: Any, esquema: dict, ruta: str = "") -> list[dict]:
    """Valida únicamente el subconjunto JSON Schema usado arriba.

    Si agregas nuevas palabras de JSON Schema, amplía este validador también.
    """
    errores = []

    def error(mensaje):
        errores.append({"campo": ruta or "$", "problema": mensaje})

    tipos = esquema["type"]
    tipos = [tipos] if isinstance(tipos, str) else tipos
    comprobaciones = {
        "null": valor is None, "string": isinstance(valor, str),
        "boolean": type(valor) is bool, "number": _numero(valor),
        "integer": type(valor) is int, "object": isinstance(valor, dict),
        "array": isinstance(valor, list),
    }
    if not any(comprobaciones[t] for t in tipos):
        error(f"Tipo inválido; se esperaba {tipos}.")
        return errores
    if "enum" in esquema and valor not in esquema["enum"]:
        error(f"Valor fuera de {esquema['enum']}.")
    if isinstance(valor, dict):
        campos = esquema["properties"]
        for c in esquema.get("required", []):
            if c not in valor:
                errores.append({"campo": f"{ruta}.{c}".strip("."),
                                "problema": "Campo requerido ausente."})
        for c, v in valor.items():
            subruta = f"{ruta}.{c}".strip(".")
            if c not in campos:
                errores.append({"campo": subruta, "problema": "Campo no previsto."})
            else:
                errores.extend(_validar_esquema(v, campos[c], subruta))
    elif isinstance(valor, list):
        if len(valor) < esquema.get("minItems", 0):
            error("La lista tiene menos elementos de los requeridos.")
        if len(valor) > esquema.get("maxItems", math.inf):
            error("La lista supera el máximo permitido.")
        for i, v in enumerate(valor):
            errores.extend(_validar_esquema(v, esquema["items"], f"{ruta}.{i}"))
    elif isinstance(valor, str):
        if len(valor.strip()) < esquema.get("minLength", 0):
            error("El texto no puede estar vacío.")
    elif _numero(valor):
        if valor < esquema.get("minimum", -math.inf):
            error("Número menor al mínimo permitido.")
        if valor > esquema.get("maximum", math.inf):
            error("Número mayor al máximo permitido.")
        if "exclusiveMinimum" in esquema and valor <= esquema["exclusiveMinimum"]:
            error("El número debe ser positivo.")
    return errores


def cita_presente(cita: str, mensaje: str) -> bool:
    """Tolera mayúsculas y espacios; conserva palabras, números y negaciones."""
    normalizar = lambda texto: " ".join(texto.casefold().split())
    cita_normalizada = normalizar(cita)
    return bool(cita_normalizada) and cita_normalizada in normalizar(mensaje)


def validar_estructura(agente: str, datos: Any) -> list[dict]:
    """Errores que impiden manejar con seguridad la respuesta del modelo."""
    return [{"agente": agente, **e}
            for e in _validar_esquema(datos, ESQUEMAS[agente])]


def _validar_citas(datos: Any, mensaje: str, ruta: str = "") -> list[dict]:
    errores = []
    if isinstance(datos, dict):
        for clave, valor in datos.items():
            campo = f"{ruta}.{clave}".strip(".")
            if clave in {"evidencia", "cita", "reemplaza_evidencia", "condicion_texto"} or (
                    clave == "texto" and ruta.endswith("condicion")):
                if isinstance(valor, str) and not cita_presente(valor, mensaje):
                    errores.append({"campo": campo,
                                    "problema": "La cita no coincide con el mensaje, incluso ignorando mayúsculas y espacios."})
            errores.extend(_validar_citas(valor, mensaje, campo))
    elif isinstance(datos, list):
        for i, valor in enumerate(datos):
            errores.extend(_validar_citas(valor, mensaje, f"{ruta}.{i}"))
    return errores


def validar_agente(agente: str, datos: Any, mensaje_original: str) -> list[dict]:
    """Valida la respuesta ORIGINAL del modelo, antes de asignar IDs/calcular.

    Retorna [] si no detecta errores. No completa campos faltantes ni convierte
    números escritos como texto. El auditor revisará la fidelidad semántica.
    """
    errores = _validar_esquema(datos, ESQUEMAS[agente])
    if not errores:
        # El auditor comunica hallazgos por ID/campo; su explicación no constituye
        # evidencia nueva. Las citas de los especialistas sí se verifican.
        if agente != "agente_3":
            errores.extend(_validar_citas(datos, mensaje_original))
        if agente == "agente_1":
            hay_calculo = any("calculo" in x for x in datos["solicitudes"])
            if (datos["accion"] == "CALCULAR") != hay_calculo:
                errores.append({"campo": "accion", "problema": "La acción no coincide con los cálculos solicitados."})
            for i, item in enumerate(datos["solicitudes"]):
                def agregar(campo, problema):
                    errores.append({"campo": f"solicitudes.{i}.{campo}", "problema": problema})
                if "rango" in item:
                    r = item["rango"]
                    if r["minimo"] > r["maximo"]:
                        agregar("rango", "El mínimo supera al máximo.")
                    if item["cantidad"] is not None or "calculo" in item:
                        agregar("rango", "Un rango conserva cantidad null y no lleva cálculo.")
                if "calculo" in item:
                    c = item["calculo"]
                    if item["cantidad"] is not None:
                        agregar("cantidad", "Debe ser null antes de ejecutar la calculadora.")
                    if c["tipo"] == "DIFERENCIA" and len(c["operandos"]) != 2:
                        agregar("calculo", "DIFERENCIA requiere exactamente dos operandos.")
                    if c["unidad_resultado"] != item["unidad"]:
                        agregar("unidad", "La unidad no coincide con la unidad del resultado.")
                if "presentacion_logistica" in item:
                    p = item["presentacion_logistica"]
                    if p["unidad_contenido"] != item["unidad"]:
                        agregar("unidad", "Con presentación, la cantidad representa el contenido total y usa su unidad.")
                    if "calculo" not in item:
                        try:
                            total = calcular("PRODUCTO", [p["cantidad_envases"], p["contenido_por_envase"]])
                            if item["cantidad"] != total:
                                agregar("cantidad", "La cantidad debe coincidir con el contenido total del empaque o solicitar un cálculo.")
                        except ValueError as exc:
                            agregar("presentacion_logistica", str(exc))
                if "condicion" in item:
                    c = item["condicion"]
                    alternativa = c["efecto"] == "ALTERNATIVA"
                    if alternativa != (c["reemplaza_evidencia"] is not None):
                        agregar("condicion", "Solo ALTERNATIVA requiere reemplaza_evidencia.")
        elif agente == "agente_2":
            u = datos["urgencia"]
            if u["nivel"] is not None and u["motivo_principal"] is None:
                errores.append({"campo": "urgencia.motivo_principal", "problema": "Falta justificar el nivel."})
        else:
            corregir = datos["accion"] == "CORREGIR"
            if corregir != bool(datos["errores"]):
                errores.append({"campo": "errores", "problema": "CORREGIR exige errores; las otras acciones exigen lista vacía."})
            if datos["accion"] == "REVISION_MANUAL" and not datos["pendientes_revision"]:
                errores.append({"campo": "pendientes_revision", "problema": "Falta explicar la revisión manual."})
            for e in datos["errores"]:
                prefijo = "suministros." if e["agente"] == "agente_1" else "contexto."
                if not e["campo"].startswith(prefijo):
                    errores.append({"campo": "errores", "problema": "La ruta no corresponde al agente responsable."})
    return [{"agente": agente, **e} for e in errores]


# 3. IDENTIFICADORES: estables ante reordenación o cambio de cantidad.
def asignar_ids(datos: dict, agente: str, id_mensaje: str) -> dict:
    """Usar después de validar. No deduplica solicitudes parecidas.

    La identidad depende del mensaje, recurso/tipo, evidencia y condición.
    Cambiar esas partes crea un ID nuevo: el coordinador debe registrar el cambio.
    Las reparaciones dirigidas deben preservar explícitamente su ID de destino.
    """
    salida = copy.deepcopy(datos)
    campo, prefijo = {"agente_1": ("solicitudes", "s"),
                      "agente_2": ("requerimientos_operativos", "o")}[agente]
    ocurrencias = {}
    for item in salida[campo]:
        identidad = [id_mensaje, agente, item.get("recurso", item.get("tipo")),
                     item["evidencia"], item.get("condicion", item.get("condicion_texto"))]
        clave = json.dumps(identidad, ensure_ascii=False, sort_keys=True)
        ocurrencias[clave] = ocurrencias.get(clave, 0) + 1
        huella = hashlib.sha256(clave.encode("utf-8")).hexdigest()[:20]
        item["id"] = f"{prefijo}_{huella}_{ocurrencias[clave]}"
    return salida


# 4. CALCULADORA: operaciones tipadas, sin eval ni interpretación de texto.
def calcular(tipo: str, operandos: list) -> int | float:
    if not isinstance(operandos, list) or not 2 <= len(operandos) <= 16:
        raise ValueError("Se requieren entre 2 y 16 operandos.")
    if not all(_numero(x) and x >= 0 for x in operandos):
        raise ValueError("Los operandos deben ser números finitos no negativos.")
    if tipo not in ("DIFERENCIA", "PRODUCTO"):
        raise ValueError(f"Operación no soportada: {tipo}")
    if tipo == "DIFERENCIA" and len(operandos) != 2:
        raise ValueError("DIFERENCIA requiere dos operandos.")
    numeros = [Decimal(str(x)) for x in operandos]
    with localcontext() as ctx:
        # Suficiente para los dígitos y exponentes de todos los operandos.
        ctx.prec = max(28, sum(len(n.as_tuple().digits) + abs(n.as_tuple().exponent)
                               for n in numeros) + 8)
        resultado = numeros[0]
        for n in numeros[1:]:
            resultado = resultado - n if tipo == "DIFERENCIA" else resultado * n
    if resultado < 0:
        raise ValueError("El resultado es negativo; revisar cantidades o interpretación.")
    if resultado == resultado.to_integral_value():
        return int(resultado)
    valor = float(resultado)
    if not math.isfinite(valor) or Decimal(str(valor)) != resultado:
        raise ValueError("El resultado no se representa fielmente como número JSON.")
    return valor


def calcular_suministros(suministros: dict) -> tuple[dict, list[dict]]:
    """Recibe extracción validada con IDs. Retorna copia y registro por operación.

    Ante un error conserva cantidad null y registra ERROR. El coordinador debe
    bloquear la aprobación hasta resolverlo. Nunca ejecuta dos veces sobre la
    copia ya calculada: conserva la extracción original para cada revisión.
    """
    salida = copy.deepcopy(suministros)
    registros = []
    for item in salida["solicitudes"]:
        if "calculo" not in item:
            continue
        operacion = item["calculo"]
        registro = {"herramienta": "calculadora", "id_destino": item["id"],
                    **copy.deepcopy(operacion), "estado": "ERROR", "resultado": None}
        try:
            if item["cantidad"] is not None:
                raise ValueError("La cantidad debe ser null antes del cálculo.")
            resultado = calcular(operacion["tipo"], operacion["operandos"])
            if operacion["unidad_resultado"] != item["unidad"]:
                raise ValueError("Unidad del resultado incompatible con la solicitud.")
            if "presentacion_logistica" in item:
                p = item["presentacion_logistica"]
                total = calcular("PRODUCTO", [p["cantidad_envases"], p["contenido_por_envase"]])
                if total != resultado or p["unidad_contenido"] != item["unidad"]:
                    raise ValueError("El cálculo no coincide con la presentación logística.")
            item["cantidad"] = resultado
            registro.update(estado="OK", resultado=resultado)
        except ValueError as exc:
            registro["error"] = str(exc)
        registros.append(registro)
    return salida, registros


# 5. ENLACES: no decide si una condición se cumple ni activa un despacho.
def resolver_alternativas(suministros: dict) -> tuple[dict, list[dict]]:
    """Devuelve mapa id_alternativa -> id_original y problemas no resueltos.

    Exige coincidencia literal única con la evidencia de la solicitud original.
    Rechaza autorreferencias, cadenas y ciclos; esos casos requieren revisión.
    Varias alternativas pueden referir a un mismo principal: no se activan aquí.
    """
    enlaces, errores = {}, []
    solicitudes = suministros["solicitudes"]
    for item in solicitudes:
        condicion = item.get("condicion")
        if not condicion or condicion["efecto"] != "ALTERNATIVA":
            continue
        candidatos = [x for x in solicitudes
                      if x["evidencia"] == condicion["reemplaza_evidencia"]]
        if len(candidatos) != 1 or candidatos[0]["id"] == item["id"]:
            errores.append({"agente": "agente_1", "id_destino": item["id"],
                            "campo": "suministros.solicitudes.condicion.reemplaza_evidencia",
                            "problema": "No existe un destino único distinto de la propia alternativa."})
        else:
            enlaces[item["id"]] = candidatos[0]["id"]
    for origen, destino in list(enlaces.items()):
        if destino in enlaces:
            errores.append({"agente": "agente_1", "id_destino": origen,
                            "campo": "suministros.solicitudes.condicion",
                            "problema": "Cadena o ciclo de alternativas: requiere revisión explícita."})
    if errores:
        # No publicar enlaces parcialmente válidos como si el conjunto fuera válido.
        return {}, errores
    return enlaces, []


def validar_destinos_auditor(auditoria: dict, suministros: dict,
                             contexto: dict) -> list[dict]:
    """Comprueba que una corrección no apunte a un ID inexistente o a otro agente."""
    ids = {
        "agente_1": {x["id"] for x in suministros["solicitudes"]},
        "agente_2": {x["id"] for x in contexto["requerimientos_operativos"]},
    }
    errores = []
    for e in auditoria["errores"]:
        if e["id_destino"] is not None and e["id_destino"] not in ids[e["agente"]]:
            errores.append({"agente": "agente_3", "campo": "errores.id_destino",
                            "problema": f"ID de corrección desconocido: {e['id_destino']}"})
    return errores


if __name__ == "__main__":
    print("herramientas.py cargado. Este módulo lo importará el coordinador.")
    print("No llama al modelo ni ejecuta los 21 casos por sí solo.")
