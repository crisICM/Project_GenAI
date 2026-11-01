"""Vista humana de los traces; biblioteca estándar, sin llamadas a modelos.

Convertir una corrida anterior:
    python traces_legibles.py Outputs_D3/run_.../traces
También admite un archivo JSON o la carpeta run_... completa.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

AGENTES = {'agente_1': 'Agente 1 - Suministros',
           'agente_2': 'Agente 2 - Contexto', 'agente_3': 'Agente 3 - Auditor'}
ETIQUETAS = {
    'mensaje_original': 'Mensaje original', 'accion': 'Acción',
    'solicitudes': 'Solicitudes', 'exclusiones': 'Exclusiones', 'dudas': 'Dudas',
    'suministros': 'Extracción de suministros', 'contexto': 'Extracción de contexto',
    'resultados_herramientas': 'Resultados de herramientas',
    'errores_validacion': 'Errores de validación enviados al auditor',
    'observaciones_auditor': 'Observaciones del auditor', 'destino': 'Campo destino',
    'valor_actual': 'Valor actual', 'extraccion_actual': 'Extracción actual del agente',
    'respuesta_anterior': 'Respuesta anterior', 'errores_a_reparar': 'Errores a reparar',
    'valor': 'Valor propuesto', 'evidencia': 'Evidencia literal', 'motivo': 'Motivo',
    'id_destino': 'ID del elemento destino', 'id': 'ID asignado por Python',
    'pendientes_revision': 'Pendientes de revisión', 'campo': 'Campo',
    'instruccion': 'Instrucción', 'problema': 'Problema', 'recurso': 'Recurso',
    'cantidad': 'Cantidad', 'unidad': 'Unidad', 'errores': 'Errores',
    'ubicacion': 'Ubicación', 'direccion_objetivo': 'Dirección objetivo',
    'referencias_acceso': 'Referencias de acceso', 'referencias': 'Referencias',
    'requerimientos_operativos': 'Requerimientos operativos', 'urgencia': 'Urgencia',
    'es_adicion': '¿Es una adición?', 'permite_eliminar': '¿Permite eliminar?',
    'registros': 'Operaciones ejecutadas', 'enlaces': 'Relaciones entre alternativas',
    'calculo': 'Cálculo declarado', 'operandos': 'Operandos',
}

def _leer_json(valor):
    if not isinstance(valor, str):
        return valor
    try:
        return json.loads(valor)
    except (ValueError, TypeError):
        return valor


def _valor(valor):
    if valor is None:
        return 'null (sin dato)'
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    return str(valor)


def _mostrar(valor, nivel=0):
    """Conserva los datos completos, incluidos cantidades, citas e IDs."""
    margen = '  ' * nivel
    lineas = []
    if isinstance(valor, dict):
        if not valor:
            return [margen + '(ninguno)']
        for clave, dato in valor.items():
            nombre = ETIQUETAS.get(clave, clave.replace('_', ' ').capitalize())
            if isinstance(dato, (dict, list)):
                lineas.append(margen + nombre + ':')
                lineas.extend(_mostrar(dato, nivel + 1))
            else:
                fragmentos = _valor(dato).splitlines() or ['']
                lineas.append(margen + nombre + ': ' + fragmentos[0])
                lineas.extend(margen + '  ' + x for x in fragmentos[1:])
    elif isinstance(valor, list):
        if not valor:
            return [margen + '(ninguno)']
        for i, dato in enumerate(valor, 1):
            if isinstance(dato, (dict, list)):
                lineas.append(margen + f'Elemento {i}:')
                lineas.extend(_mostrar(dato, nivel + 1))
            else:
                lineas.extend(margen + '- ' + x for x in _valor(dato).splitlines())
    else:
        lineas.extend(margen + x for x in _valor(valor).splitlines())
    return lineas


def ruta_legible(ruta_trace):
    ruta = Path(ruta_trace)
    return ruta.parent.parent / 'traces_v1' / (ruta.stem + '.txt')


def renderizar_trace(trace):
    lineas = ['TRAZA LEGIBLE - ' + str(trace.get('id_mensaje', 'Sin identificador')), '',
              'Registro de mensajes y decisiones observadas. No contiene esquemas,',
              'ejemplos del system prompt, tiempos, tokens ni huellas técnicas.',
              'Una validación sin errores no garantiza una interpretación correcta.', '',
              'MENSAJE ORIGINAL', *(_mostrar(trace.get('mensaje_original', ''))), '']
    paso = 0
    ultima_respuesta = None
    hay_resultado = False

    def seccion(titulo, datos=None, nota=None):
        nonlocal paso
        paso += 1
        lineas.extend([f'PASO {paso:02d} | {titulo}', '-' * 70])
        if nota:
            lineas.append(nota)
        if datos is not None:
            lineas.extend(_mostrar(datos))
        lineas.append('')

    def resultado(datos):
        seccion('CIERRE - Python construye el resultado', {
            'estado': datos.get('estado', 'No informado'),
            'salida_4_claves': datos.get('salida_4_claves'),
            'vista_4_provisional': datos.get('vista_4_provisional'),
            'pendientes_revision': datos.get('pendientes_revision', []),
        }, 'El estado es técnico. VALIDADA no equivale a ausencia garantizada de errores.')

    for e in trace.get('eventos', []):
        tipo = e.get('tipo')
        agente = AGENTES.get(e.get('agente'), e.get('agente', 'Agente'))
        if tipo == 'inicio':
            continue
        if tipo == 'llamada_iniciada':
            modo = ('corrección local' if e.get('modo') == 'correccion' else
                    'auditoría' if e.get('agente') == 'agente_3' else 'extracción')
            mensajes = e.get('peticion', {}).get('messages', [])
            entrada = [_leer_json(m.get('content', '')) for m in mensajes if m.get('role') != 'system']
            reintento = f"; reintento {e['intento']}" if e.get('intento', 0) else ''
            seccion(f'{agente} — Entrada recibida ({modo}{reintento})',
                    entrada[0] if len(entrada) == 1 else entrada,
                    'Datos recibidos por el agente (instrucciones system omitidas):')
        elif tipo == 'respuesta_modelo':
            respuesta = e.get('respuesta', {}).get('message', {}).get('content')
            ultima_respuesta = _leer_json(respuesta)
            seccion(f'{agente} — Respuesta generada', ultima_respuesta,
                    'Respuesta del modelo:' if respuesta is not None else 'No hay contenido de respuesta.')
        elif tipo == 'validacion':
            errores = e.get('errores', [])
            seccion(f'Python valida la respuesta de {agente}',
                    {'errores': errores} if errores else None,
                    None if errores else 'Sin errores detectados por esta validación. No certifica exactitud semántica.')
        elif tipo == 'extraccion_aceptada':
            ids = {k: [x.get('id') for x in v if isinstance(x, dict) and 'id' in x]
                   for k, v in e.get('datos', {}).items() if isinstance(v, list)}
            ids = {k: v for k, v in ids.items() if v}
            seccion(f'Python guarda la extracción de {agente}', ids or None,
                    'Se conserva la respuesta anterior como estado de trabajo. IDs añadidos por Python:')
        elif tipo == 'herramientas':
            seccion('Python ejecuta herramientas sobre el estado actual',
                    {k: e.get(k, defecto) for k, defecto in
                     [('accion_agente_1', None), ('registros', []), ('enlaces', {}), ('errores', [])]})
        elif tipo == 'decision_auditor':
            a = e.get('auditoria', {})
            ronda = e.get('ronda', 0)
            revision = 'inicial' if ronda == 0 else f'después de la ronda de corrección {ronda}'
            # La respuesta completa ya aparece en el evento respuesta_modelo.
            nota = f"Decisión registrada: {a.get('accion', '(ausente)')}."
            if a.get('accion') == 'CORREGIR':
                nota += ' El auditor solicita cambios; los eventos posteriores indican cuáles se aplican.'
            elif a.get('accion') == 'APROBAR':
                nota += ' El cierre depende también de los controles Python.'
            elif a.get('accion') == 'REVISION_MANUAL':
                nota += ' Se registran pendientes para revisión.'
            seccion(f'Decisión del auditor — revisión {revision}',
                    None if a == ultima_respuesta else a, nota)
        elif tipo == 'correccion_aplicada':
            seccion(f'Python aplica la corrección de {agente}', {
                'observaciones_auditor': e.get('observacion'), 'cambio_aplicado': e.get('parche'),
                'estado_antes_del_cambio': e.get('antes'), 'estado_despues_del_cambio': e.get('despues')})
        elif tipo in ('error_transporte', 'flujo_interrumpido', 'error_ejecutor'):
            seccion('ERROR / INTERRUPCIÓN' + (f' - {agente}' if e.get('agente') else ''),
                    {'error': e.get('error', 'Sin detalle')})
        elif tipo == 'resultado':
            resultado(e)
            hay_resultado = True
        else:
            # Eventos nuevos: preservar contenido funcional sin metadatos.
            seccion('Evento: ' + str(tipo), {k: v for k, v in e.items()
                    if k not in ('tipo', 'fecha_utc', 'segundos', 'peticion', 'configuracion')})

    if not hay_resultado and isinstance(trace.get('resultado'), dict):
        resultado(trace['resultado'])
        hay_resultado = True
    if not hay_resultado:
        lineas.extend(['REGISTRO EN CURSO / SIN SALIDA FINAL',
                       'No hay resultado final registrado. La ejecución puede estar en curso o haberse interrumpido.'])
        if trace.get('estado_ejecutor'):
            lineas.append('Estado del ejecutor: ' + str(trace['estado_ejecutor']))
    return '\n'.join(lineas).rstrip() + '\n'



def guardar_trace_legible(trace, ruta_trace):
    destino = ruta_legible(ruta_trace)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix('.txt.tmp')
    temporal.write_text(renderizar_trace(trace), encoding='utf-8-sig')
    temporal.replace(destino)
    return destino


def main():
    parser = argparse.ArgumentParser(description='Crear traces_v1 desde traces JSON existentes; no usa Ollama.')
    parser.add_argument('ruta', type=Path, help='JSON, carpeta traces o carpeta run_...')
    args = parser.parse_args()
    ruta = args.ruta
    if ruta.is_file():
        archivos = [ruta]
    else:
        carpeta = ruta / 'traces' if (ruta / 'traces').is_dir() else ruta
        archivos = sorted(carpeta.glob('*.json'))
    if not archivos:
        parser.error('No se encontraron trazos JSON.')
    for archivo in archivos:
        trace = json.loads(archivo.read_text(encoding='utf-8-sig'))
        print(guardar_trace_legible(trace, archivo))


if __name__ == '__main__':
    main()
