"""
Documento extenso de la validación (docs/VALIDACION_CUANTITATIVA.md §6.2 y §7.3).

Contrato marco de prestación de servicios de 20 páginas con cuatro anexos,
ficticio, en versión vectorial y escaneada. Cubre lo que los 42 casos del Gold
Standard (1 a 3 páginas) no cubren: un documento que llena el contexto del chat
y datos repartidos en todo el texto (la pena convencional en las cláusulas, los
tiempos de respuesta en el Anexo A, el monto en el Anexo B, las deductivas en el
Anexo D y las firmas en la última página). También es el contrato de 20 páginas
del benchmark del RNF-02 (§7.3).

Va en su propia anotación (``extenso.json``, congelada con ``extenso.sha256``)
para no alterar ``gold_standard.json``, que se congeló antes de ejecutar.

Uso:  cd services/ai-service && python -m evaluacion.documento_extenso
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict

from evaluacion import gold_standard as gs

RUTA_ANOTACION = os.path.join(gs.DIRECTORIO, "extenso.json")
RUTA_HUELLA = os.path.join(gs.DIRECTORIO, "extenso.sha256")
ID = "GS-CONT-EXT"

_ORDINALES = ("PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA",
              "DÉCIMA", "DÉCIMA PRIMERA", "DÉCIMA SEGUNDA", "DÉCIMA TERCERA", "DÉCIMA CUARTA", "DÉCIMA QUINTA",
              "DÉCIMA SEXTA", "DÉCIMA SÉPTIMA", "DÉCIMA OCTAVA", "DÉCIMA NOVENA", "VIGÉSIMA", "VIGÉSIMA PRIMERA",
              "VIGÉSIMA SEGUNDA", "VIGÉSIMA TERCERA", "VIGÉSIMA CUARTA")

# (título, texto) de cada cláusula, en el orden en que aparecen.
_CLAUSULAS = [
    ("OBJETO", "EL PRESTADOR se obliga a prestar a EL CLIENTE los servicios administrados de tecnologías de la "
     "información descritos en el Anexo A, con los niveles de servicio que ahí se establecen, en las instalaciones de "
     "EL CLIENTE ubicadas en Avenida Tecnológico 2909, Colonia Centro, Chihuahua, Chihuahua."),
    ("ALCANCE", "Los servicios comprenden la mesa de ayuda, el soporte en sitio, la administración de servidores, el "
     "respaldo y la recuperación de información, la seguridad perimetral, las redes y telecomunicaciones y la gestión "
     "de licencias. Cualquier servicio adicional requerirá un convenio modificatorio firmado por ambas partes."),
    ("CONTRAPRESTACIÓN", "EL CLIENTE pagará a EL PRESTADOR la contraprestación mensual que resulta de los precios "
     "unitarios del Anexo B. Los precios se expresan en pesos mexicanos, no incluyen el Impuesto al Valor Agregado y "
     "permanecerán fijos durante la vigencia del contrato."),
    ("FORMA DE PAGO", "El pago se realizará mediante transferencia electrónica dentro de los diez días naturales "
     "siguientes a la recepción de la factura, a la cuenta que EL PRESTADOR designe por escrito. EL CLIENTE podrá "
     "retener el pago de una factura que no cumpla los requisitos fiscales hasta que sea corregida."),
    ("FACTURACIÓN", "EL PRESTADOR emitirá una factura mensual por los servicios efectivamente prestados, acompañada "
     "del reporte de niveles de servicio del mes. Las deductivas del Anexo D se descontarán en la factura del mes "
     "siguiente a aquel en que se generen."),
    ("VIGENCIA", "El presente contrato estará vigente del 2 de marzo de 2026 al 1 de marzo de 2027 y podrá "
     "renovarse por periodos iguales mediante convenio por escrito firmado con treinta días de anticipación."),
    ("TERMINACIÓN ANTICIPADA", "Cualquiera de las partes podrá dar por terminado anticipadamente el contrato "
     "mediante aviso por escrito con treinta días naturales de anticipación. EL CLIENTE pagará únicamente los "
     "servicios prestados hasta la fecha efectiva de terminación."),
    ("RESCISIÓN", "EL CLIENTE podrá rescindir el contrato sin responsabilidad si EL PRESTADOR incumple de manera "
     "reiterada los niveles de servicio durante tres meses consecutivos, previa notificación en la que se le conceda "
     "un plazo de quince días naturales para corregir el incumplimiento."),
    ("CONFIDENCIALIDAD", "Las partes se obligan recíprocamente a no divulgar la información confidencial que reciban "
     "con motivo de este contrato, durante su vigencia y dos años posteriores a su terminación, y a devolverla o "
     "destruirla al concluir los servicios."),
    ("DATOS PERSONALES", "EL PRESTADOR tratará los datos personales a los que tenga acceso únicamente como encargado, "
     "conforme a las instrucciones de EL CLIENTE y a la Ley Federal de Protección de Datos Personales en Posesión de "
     "los Particulares, y aplicará medidas de seguridad administrativas, técnicas y físicas."),
    ("PROPIEDAD INTELECTUAL", "Los desarrollos, scripts y documentación que EL PRESTADOR elabore específicamente para "
     "EL CLIENTE serán propiedad de EL CLIENTE. EL PRESTADOR conserva la titularidad de sus herramientas y "
     "metodologías previas."),
    ("PENA CONVENCIONAL", "En caso de incumplimiento de las obligaciones a su cargo, EL PRESTADOR pagará a EL CLIENTE "
     "una pena convencional equivalente al diez por ciento del monto mensual de la contraprestación por cada mes de "
     "incumplimiento, sin perjuicio de las deductivas por niveles de servicio del Anexo D."),
    ("GARANTÍA DE CUMPLIMIENTO", "EL PRESTADOR entregará, dentro de los diez días naturales siguientes a la firma, "
     "una fianza de cumplimiento por el equivalente al diez por ciento del monto anual del contrato, expedida por una "
     "institución afianzadora autorizada."),
    ("SEGUROS", "EL PRESTADOR mantendrá vigente durante la prestación de los servicios un seguro de responsabilidad "
     "civil con una suma asegurada mínima de dos millones de pesos."),
    ("PERSONAL", "EL PRESTADOR asignará personal calificado y certificado en las tecnologías objeto del servicio, y "
     "notificará por escrito cualquier sustitución del personal clave con cinco días hábiles de anticipación."),
    ("RELACIÓN LABORAL", "EL PRESTADOR es el único patrón del personal que asigne a los servicios y será responsable "
     "de las obligaciones laborales, fiscales y de seguridad social, por lo que no existirá relación laboral entre "
     "dicho personal y EL CLIENTE."),
    ("SUBCONTRATACIÓN", "EL PRESTADOR no podrá subcontratar total ni parcialmente los servicios sin la autorización "
     "previa y por escrito de EL CLIENTE; en su caso, seguirá siendo responsable frente a EL CLIENTE de los servicios "
     "subcontratados."),
    ("CESIÓN DE DERECHOS", "Ninguna de las partes podrá ceder sus derechos u obligaciones derivados de este contrato "
     "sin el consentimiento previo y por escrito de la otra."),
    ("CASO FORTUITO O FUERZA MAYOR", "Ninguna de las partes será responsable por el incumplimiento causado por caso "
     "fortuito o fuerza mayor debidamente acreditado; la parte afectada lo notificará a la otra dentro de los tres "
     "días hábiles siguientes."),
    ("SUPERVISIÓN", "EL CLIENTE designará a un administrador del contrato, que verificará el cumplimiento de los "
     "niveles de servicio y aprobará los reportes mensuales."),
    ("NOTIFICACIONES", "Las notificaciones se harán por escrito en los domicilios señalados en las declaraciones o "
     "por correo electrónico con acuse de recibo a las direcciones que las partes designen en el Anexo C."),
    ("MODIFICACIONES", "Cualquier modificación a este contrato o a sus anexos deberá constar en un convenio "
     "modificatorio firmado por los representantes de ambas partes."),
    ("ANEXOS", "Forman parte integrante de este contrato el Anexo A (catálogo de servicios y niveles de servicio), el "
     "Anexo B (precios), el Anexo C (matriz de escalamiento) y el Anexo D (deductivas)."),
    ("JURISDICCIÓN", "Para la interpretación y cumplimiento de este contrato, las partes se someten a los tribunales "
     "competentes de la ciudad de Chihuahua, Chihuahua, y renuncian a cualquier otro fuero."),
]

# (servicio, descripción, [(prioridad, respuesta, solución)], indicador, meta)
_SERVICIOS = [
    ("MESA DE AYUDA", "Atención de solicitudes e incidentes de los usuarios por teléfono, correo y portal, con "
     "registro de cada caso en la herramienta de gestión de EL PRESTADOR.",
     [("Crítica", "15 minutos", "4 horas"), ("Alta", "30 minutos", "8 horas"), ("Media", "2 horas", "2 días hábiles"),
      ("Baja", "4 horas", "5 días hábiles")], "Casos resueltos en el primer contacto", "70 % mensual"),
    ("SOPORTE EN SITIO", "Atención presencial de equipos de cómputo, impresoras y periféricos en las instalaciones "
     "de EL CLIENTE, de lunes a viernes de 8:00 a 18:00 horas.",
     [("Crítica", "1 hora", "6 horas"), ("Alta", "2 horas", "1 día hábil"), ("Media", "4 horas", "3 días hábiles"),
      ("Baja", "1 día hábil", "5 días hábiles")], "Satisfacción de los usuarios", "85 % en la encuesta mensual"),
    ("ADMINISTRACIÓN DE SERVIDORES", "Monitoreo, parches, respaldos de configuración y administración de los "
     "servidores físicos y virtuales del centro de datos de EL CLIENTE.",
     [("Crítica", "15 minutos", "2 horas"), ("Alta", "30 minutos", "6 horas"), ("Media", "2 horas", "1 día hábil"),
      ("Baja", "4 horas", "3 días hábiles")], "Disponibilidad de los servidores", "99.5 % mensual"),
    ("RESPALDO Y RECUPERACIÓN", "Respaldo diario incremental y semanal completo de las bases de datos y los "
     "servidores de archivos, con pruebas de restauración trimestrales.",
     [("Crítica", "30 minutos", "4 horas"), ("Alta", "1 hora", "8 horas"), ("Media", "4 horas", "2 días hábiles"),
      ("Baja", "1 día hábil", "5 días hábiles")], "Respaldos concluidos con éxito", "98 % mensual"),
    ("SEGURIDAD PERIMETRAL", "Administración del cortafuegos, la red privada virtual y el filtrado de contenido, "
     "con revisión semanal de bitácoras y reporte de eventos de seguridad.",
     [("Crítica", "15 minutos", "2 horas"), ("Alta", "30 minutos", "4 horas"), ("Media", "2 horas", "1 día hábil"),
      ("Baja", "4 horas", "3 días hábiles")], "Eventos críticos atendidos en tiempo", "100 % mensual"),
    ("REDES Y TELECOMUNICACIONES", "Administración de conmutadores, puntos de acceso inalámbrico y enlaces de "
     "comunicación entre sucursales.",
     [("Crítica", "30 minutos", "4 horas"), ("Alta", "1 hora", "8 horas"), ("Media", "4 horas", "2 días hábiles"),
      ("Baja", "1 día hábil", "5 días hábiles")], "Disponibilidad de la red", "99.7 % mensual"),
    ("GESTIÓN DE LICENCIAS", "Inventario, renovación y asignación de las licencias de software de EL CLIENTE, con "
     "reporte trimestral de licencias por vencer.",
     [("Alta", "1 día hábil", "3 días hábiles"), ("Media", "2 días hábiles", "5 días hábiles")],
     "Licencias renovadas antes de su vencimiento", "100 % trimestral"),
]

_PRECIOS = [("Mesa de ayuda", "38,500.00"), ("Soporte en sitio", "31,000.00"),
            ("Administración de servidores", "42,000.00"), ("Respaldo y recuperación", "21,500.00"),
            ("Seguridad perimetral", "24,000.00"), ("Redes y telecomunicaciones", "19,500.00"),
            ("Gestión de licencias", "8,500.00")]


def paginas() -> list[list[str]]:
    t, p = gs.TITULAR, gs.PRESTADOR
    resultado: list[list[str]] = [[
        "# CONTRATO MARCO DE PRESTACIÓN DE SERVICIOS ADMINISTRADOS DE TECNOLOGÍAS DE LA INFORMACIÓN",
        "",
        f"Contrato que celebran, por una parte, {t['razon_social']}, con RFC {t['rfc']}, en lo sucesivo EL CLIENTE,",
        f"representada por {gs.APODERADA}, y por la otra, {p['razon_social']}, con RFC {p['rfc']},",
        f"en lo sucesivo EL PRESTADOR, representada por {gs.REP_PRESTADOR}, al tenor de las siguientes:",
        "",
        "# DECLARACIONES",
        "I. Declara EL CLIENTE, por conducto de su apoderada, que:",
        "a) Es una sociedad mercantil constituida conforme a las leyes mexicanas, según consta en la escritura pública",
        "número 12,845 otorgada ante el Notario Público número 27 de Chihuahua, inscrita en el Registro Público de",
        "Comercio bajo el Folio Mercantil Electrónico número 48213*1.",
        "b) Su apoderada cuenta con facultades suficientes para obligarla, según la escritura pública número 20,117.",
        "c) Requiere contratar servicios administrados de tecnologías de la información para sus oficinas.",
        "II. Declara EL PRESTADOR, por conducto de su representante legal, que:",
        "a) Es una sociedad mercantil constituida conforme a las leyes mexicanas, con domicilio en Monterrey, Nuevo",
        "León, y cuenta con la capacidad técnica, el personal y los recursos necesarios para prestar los servicios.",
        "b) Su representante legal cuenta con facultades suficientes para obligarla.",
        "III. Declaran ambas partes que se reconocen la personalidad con que comparecen y que es su voluntad celebrar",
        "este contrato, al tenor de las siguientes:",
    ]]
    bloques = [[f"# {_ORDINALES[i]}. {titulo}.", texto, ""] for i, (titulo, texto) in enumerate(_CLAUSULAS)]
    for inicio in range(0, len(bloques), 3):                                   # 8 páginas de cláusulas
        resultado.append(["# CLÁUSULAS"] + [r for b in bloques[inicio:inicio + 3] for r in b])
    for numero, (servicio, descripcion, niveles, indicador, meta) in enumerate(_SERVICIOS, start=1):
        pagina = ["# ANEXO A. CATÁLOGO DE SERVICIOS Y NIVELES DE SERVICIO", "",
                  f"# A.{numero} {servicio}", descripcion, "", "Niveles de servicio por prioridad del incidente:"]
        pagina += [f"Prioridad {pr}: tiempo de respuesta de {resp}; tiempo de solución de {sol}."
                   for pr, resp, sol in niveles]
        pagina += ["", f"Indicador de desempeño: {indicador}. Meta: {meta}.",
                   "El tiempo de respuesta se mide desde el registro del incidente en la herramienta de gestión hasta",
                   "la primera atención de un especialista; el tiempo de solución, hasta el restablecimiento del",
                   "servicio confirmado por el usuario.", "",
                   "Exclusiones: fallas causadas por equipos sin garantía del fabricante, por modificaciones realizadas",
                   "por terceros no autorizados o por la falta de suministro eléctrico en las instalaciones."]
        resultado.append(pagina)                                               # 7 páginas
    resultado.append(["# ANEXO B. PRECIOS", "",
                      "Precios mensuales por servicio, en pesos mexicanos, sin el Impuesto al Valor Agregado:", ""]
                     + [f"{s}: ${m} M.N." for s, m in _PRECIOS]
                     + ["", "Monto mensual total de los servicios: $185,000.00 (ciento ochenta y cinco mil pesos "
                            "00/100 M.N.) más el Impuesto al Valor Agregado.",
                        "Monto anual del contrato: $2,220,000.00 más el Impuesto al Valor Agregado.", "",
                        "Los precios incluyen el personal, las herramientas de gestión y los traslados dentro de la",
                        "ciudad de Chihuahua. No incluyen refacciones, licencias nuevas ni equipos adicionales."])
    resultado.append(["# ANEXO C. MATRIZ DE ESCALAMIENTO", "",
                      "Nivel 1: Mesa de ayuda de EL PRESTADOR, disponible las 24 horas en el teléfono 614 410 2200.",
                      "Nivel 2: Coordinador del servicio, Ing. Samuel Cárdenas Olvera, correo scardenas@ejemplo.mx.",
                      "Nivel 3: Gerente de cuenta, Lic. Patricia Nájera Fuentes, correo pnajera@ejemplo.mx.",
                      f"Nivel 4: Representante legal de EL PRESTADOR, {gs.REP_PRESTADOR}.", "",
                      "Por EL CLIENTE, el administrador del contrato es el Ing. Tomás Ugalde Rivas, Gerente de",
                      "Tecnologías de la Información, correo tugalde@ejemplo.mx.", "",
                      "Un incidente de prioridad crítica sin respuesta en su tiempo de respuesta se escala",
                      "automáticamente al nivel siguiente, y así sucesivamente cada media hora."])
    resultado.append(["# ANEXO D. DEDUCTIVAS POR NIVELES DE SERVICIO", "",
                      "Las deductivas se calculan sobre el precio mensual del servicio afectado:", "",
                      "Disponibilidad de los servidores menor a 99.5 % y hasta 99.0 %: cinco por ciento.",
                      "Disponibilidad de los servidores menor a 99.0 %: diez por ciento.",
                      "Disponibilidad de la red menor a 99.7 %: cinco por ciento.",
                      "Respaldos concluidos con éxito por debajo del 98 %: tres por ciento.",
                      "Incidentes críticos de la mesa de ayuda sin respuesta en 15 minutos: uno por ciento por caso.",
                      "", "La suma de las deductivas de un mes no excederá el veinte por ciento del monto mensual",
                      "total. Las deductivas son independientes de la pena convencional pactada en las cláusulas."])
    resultado.append(["# FIRMAS", "",
                      "Leído que fue el presente contrato y enteradas las partes de su contenido y alcance legal, lo",
                      "firman por duplicado en la ciudad de Chihuahua, Chihuahua, el 2 de marzo de 2026.", "",
                      "# EL CLIENTE", t["razon_social"], f"{gs.APODERADA}, Apoderada legal", "",
                      "# EL PRESTADOR", p["razon_social"], f"{gs.REP_PRESTADOR}, Representante legal"])
    return resultado


def caso() -> gs.Caso:
    return gs.Caso(
        ID, "CONTRATO_SERVICIOS", "Contrato marco de 20 páginas con cuatro anexos", paginas(),
        gs.Esperado(
            tipo_documento="CONTRATO", rfc=gs.TITULAR["rfc"], razon_social=gs.TITULAR["razon_social"],
            fecha_emision="2026-03-02", fecha_vencimiento="2027-03-01", estatus="EN_REVISION",
            motivo="Todas las cláusulas presentes; el contrato identifica a sus firmantes y RSC-02 deja la decisión "
                   "al analista (DOC-05).",
            personas=gs._personas((gs.APODERADA, "Apoderada legal"), (gs.REP_PRESTADOR, "Representante legal")),
            elementos={k: True for k in gs._CONT_TODO},
        ),
        escaneado=True,
    )


def generar() -> None:
    c = caso()
    assert len(c.paginas) == 20, len(c.paginas)
    os.makedirs(gs.DIRECTORIO_DOCUMENTOS, exist_ok=True)
    vectorial = gs.pdf_vectorial(c)
    salida = []
    for rendicion, sufijo, contenido in (("VECTORIAL", "", vectorial),
                                         ("ESCANEADO", "-ESC", gs.pdf_escaneado(c, vectorial, gris=True))):
        archivo = c.archivo.replace(".pdf", f"{sufijo.lower()}.pdf")
        with open(os.path.join(gs.DIRECTORIO_DOCUMENTOS, archivo), "wb") as f:
            f.write(contenido)
        salida.append({
            "id": c.id + sufijo, "caso_base": c.id, "archivo": archivo, "rendicion": rendicion,
            "tipo_registrado": c.tipo_registrado, "descripcion": c.descripcion, "titular": c.titular,
            "sello_notarial": False, "paginas": len(c.paginas), "esperado": asdict(c.esperado),
            "sha256_archivo": hashlib.sha256(contenido).hexdigest(), "texto_referencia": gs.texto_de_referencia(c),
        })
    with open(RUTA_ANOTACION, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"version": 1, "fecha_referencia": gs.FECHA_REFERENCIA.isoformat(), "titular": gs.TITULAR,
                   "casos": salida}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(RUTA_ANOTACION, "rb") as f:
        huella = hashlib.sha256(f.read()).hexdigest()
    with open(RUTA_HUELLA, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{huella}  extenso.json\n")
    print(f"[documento extenso] {len(c.paginas)} páginas; extenso.json sha256 {huella}")


if __name__ == "__main__":
    generar()
