"""
Script de precarga del catálogo base de Reglas de Validación (DOC-05).
Inserta en PostgreSQL las reglas RIE-01, RIE-02, RIE-03 y RCV-01, tal como
están definidas textualmente en el "Catálogo Formal de Reglas de Negocio"
del DOC-05 (Estrategia de Validación y Catálogo de Reglas de Negocio), y
RCV-02: la "Caducidad Estricta de Documentos con Vigencia Legal Fija" del
mismo catálogo, aplicada al comprobante de domicilio fiscal con el límite
"no mayor a 3 meses" del DOC-02 (90 días naturales, DOC-08), y RCV-03, la
misma caducidad para la constancia de situación fiscal (DOC-02, Tabla 2). Carga también
las reglas RIE-01-CSF, RIE-01-DOM y RIE-01-ACTA, que declaran los tres tipos de
documento obligatorios del expediente corporativo (DOC-02, Tabla 3), y las
reglas equivalentes de los expedientes jurídico (Tabla 4) y regulatorio
(Tabla 5): el inventario obligatorio depende del tipo de expediente (RF-06).
Por último, RIE-02-CONT-ANX vincula los anexos legales al contrato de
prestación de servicios (RIE-02, RF-07). Las reglas RSC declaran los elementos
de contenido que el Nivel 4 localiza en cada tipo de documento (DOC-05, RSC-01).

Extensión PLUS-03 (PRD §21.1): RCV-04 aplica la misma caducidad estricta a la
opinión de cumplimiento del artículo 32-D (30 días, el ejemplo literal del
DOC-05) y RSC-OPIN-SENT declara el sentido de la opinión, que el ai-service
lee con reglas deterministas y no con el modelo.

La precarga es idempotente: solo inserta las reglas que no existen y nunca
modifica las que el administrador ya editó. El rules-service la ejecuta al
arrancar (AUTO_SEED=true, por defecto), de modo que un despliegue nuevo con
Docker Compose tenga el catálogo completo sin pasos manuales.

Ejecuta (desde services/rules-service/): python seed_reglas_validacion.py
"""
from config.database import SessionLocal, init_db
from models.regla import Regla

REGLAS_BASE = [
    {
        "codigo_regla": "RIE-01",
        "nombre_regla": "Completitud de Expediente",
        "familia_regla": "RIE",
        "descripcion": (
            "El sistema calcula el porcentaje de documentos obligatorios "
            "presentes en el expediente respecto al total de documentos "
            "obligatorios configurados para ese tipo de expediente. Si el "
            "porcentaje es menor al 100%, el expediente no puede obtener "
            "estatus de aprobado. El sistema indica claramente cuáles "
            "documentos faltan."
        ),
        "severidad": "CRITICA",
        "accion": "Semáforo Rojo y listado de documentos faltantes.",
        "tipo_documento": None,
        "documento_obligatorio": True,
        "dias_maximos_vigencia": None,
    },
    # Inventario obligatorio por tipo de expediente (DOC-02, Tablas 3 a 5): una
    # regla RIE por tipo de documento. El core-service calcula la completitud
    # (RIE-01) a partir de estas reglas, no de una lista fija en su código
    # (HU-09 / HU-12), y solo aplica las del tipo del expediente (RF-06).
    *[
        {
            "codigo_regla": codigo,
            "nombre_regla": f"Completitud: {nombre}",
            "familia_regla": "RIE",
            "descripcion": (
                f"El expediente {etiqueta_expediente} debe contener {articulo} {nombre}. Mientras falte, "
                "el expediente no puede obtener estatus de aprobado (RIE-01)."
            ),
            "severidad": "CRITICA",
            "accion": f"Semáforo Rojo: falta {articulo} {nombre}.",
            "tipo_documento": tipo,
            "documento_obligatorio": True,
            "dias_maximos_vigencia": None,
            "tipo_expediente": tipo_expediente,
        }
        for tipo_expediente, etiqueta_expediente, codigo, tipo, articulo, nombre in [
            # Corporativo (Tabla 3): el inventario base del expediente B2B.
            ("CORPORATIVO", "corporativo", "RIE-01-CSF", "CSF_SAT", "la", "Constancia de Situación Fiscal"),
            ("CORPORATIVO", "corporativo", "RIE-01-DOM", "COMP_DOMICILIO", "el", "Comprobante de Domicilio Fiscal"),
            ("CORPORATIVO", "corporativo", "RIE-01-ACTA", "ACTA_CONSTITUTIVA", "el", "Acta Constitutiva"),
            # Jurídico (Tabla 4): documentos marcados como obligatorios.
            ("JURIDICO", "jurídico", "RIE-01-JUR-CONT", "CONTRATO_SERVICIOS", "el",
             "Contrato de Prestación de Servicios"),
            ("JURIDICO", "jurídico", "RIE-01-JUR-NDA", "ACUERDO_CONFIDENCIALIDAD", "el",
             "Acuerdo de Confidencialidad (NDA)"),
            ("JURIDICO", "jurídico", "RIE-01-JUR-PODER", "PODER_NOTARIAL", "el", "Poder Notarial del representante"),
            # Regulatorio (Tabla 5): documentos marcados como obligatorios.
            ("REGULATORIO", "regulatorio", "RIE-01-REG-LIC", "LICENCIA_OPERACION", "la", "Licencia de Operación"),
            ("REGULATORIO", "regulatorio", "RIE-01-REG-PERM", "PERMISO_SECTORIAL", "el",
             "Permiso Municipal o Sectorial"),
            ("REGULATORIO", "regulatorio", "RIE-01-REG-POL", "POLIZA_SEGURO", "la", "Póliza de Seguro"),
            ("REGULATORIO", "regulatorio", "RIE-01-REG-REGS", "REGISTRO_SECTORIAL", "el",
             "Registro ante Autoridad Sectorial"),
        ]
    ],
    # Anexo vinculado (RIE-02, RF-07): el contrato de prestación de servicios
    # exige sus anexos legales (DOC-02, Tabla 4: "presencia de los anexos
    # referenciados en el contrato principal"). Aplica a cualquier expediente
    # que contenga un contrato.
    {
        "codigo_regla": "RIE-02-CONT-ANX",
        "nombre_regla": "Anexos legales del Contrato de Prestación de Servicios",
        "familia_regla": "RIE",
        "descripcion": (
            "Si el expediente contiene un Contrato de Prestación de Servicios, debe incluir también "
            "sus anexos legales. La ausencia del anexo invalida el documento principal (RIE-02)."
        ),
        "severidad": "ALTA",
        "accion": "Semáforo Rojo con indicación específica del anexo ausente.",
        "tipo_documento": "ANEXO_CONTRATO",
        "documento_obligatorio": True,
        "dias_maximos_vigencia": None,
        "tipo_expediente": None,
        "documento_principal": "CONTRATO_SERVICIOS",
    },
    {
        "codigo_regla": "RIE-02",
        "nombre_regla": "Vinculación Obligatoria de Anexos",
        "familia_regla": "RIE",
        "descripcion": (
            "Si un documento principal (por ejemplo, un Contrato de "
            "Prestación de Servicios) requiere anexos vinculados (como una "
            "Propuesta Técnica o una Póliza de Fianza), la ausencia de "
            "cualquiera de los anexos invalida el documento principal."
        ),
        "severidad": "ALTA",
        "accion": "Semáforo Rojo con indicación específica del anexo ausente.",
        "tipo_documento": None,
        "documento_obligatorio": True,
        "dias_maximos_vigencia": None,
    },
    {
        "codigo_regla": "RIE-03",
        "nombre_regla": "Integridad Criptográfica del Archivo",
        "familia_regla": "RIE",
        "descripcion": (
            "Al consultar un documento previamente cargado, el sistema "
            "recalcula su huella criptográfica SHA-256 y la compara con el "
            "valor registrado en la base de datos al momento de la carga "
            "inicial. Si los valores no coinciden, se ha detectado una "
            "alteración no autorizada del archivo."
        ),
        "severidad": "CRITICA",
        "accion": "Bloqueo inmediato del documento y registro en bitácora de auditoría.",
        "tipo_documento": None,
        "documento_obligatorio": True,
        "dias_maximos_vigencia": None,
    },
    {
        "codigo_regla": "RCV-01",
        "nombre_regla": "Vigencia Mandatoria",
        "familia_regla": "RCV",
        "descripcion": (
            "El sistema calcula la diferencia en días entre la fecha de "
            "vencimiento del documento y la fecha actual. Si la diferencia "
            "es negativa, el documento está vencido (Severidad Alta, "
            "Semáforo Rojo). Si está entre 0 y 30 días, el documento está "
            "próximo a vencer (Severidad Media, Semáforo Amarillo). Si es "
            "mayor a 30 días, el documento está vigente (Semáforo Verde)."
        ),
        "severidad": "ALTA",
        "accion": (
            "Vencido: Semáforo Rojo. Próximo a vencer (0-30 días): Semáforo "
            "Amarillo. Vigente (>30 días): Semáforo Verde."
        ),
        "tipo_documento": None,
        "documento_obligatorio": True,
        "dias_maximos_vigencia": 30,
    },
    {
        "codigo_regla": "RCV-02",
        "nombre_regla": "Caducidad Estricta del Comprobante de Domicilio Fiscal",
        "familia_regla": "RCV",
        "descripcion": (
            "El comprobante de domicilio fiscal tiene una vigencia legal "
            "predeterminada: no puede tener más de 90 días naturales de "
            "antigüedad. El sistema calcula la diferencia entre la fecha de "
            "evaluación y la fecha de emisión del documento; si supera los 90 "
            "días, el documento se marca automáticamente como vencido y "
            "requiere actualización inmediata. Si el documento no declara "
            "fecha de emisión, la antigüedad no puede verificarse y el caso "
            "se turna a revisión humana."
        ),
        "severidad": "ALTA",
        "accion": (
            "Más de 90 días desde la emisión: documento vencido, Semáforo Rojo "
            "y solicitud de un comprobante actualizado."
        ),
        "tipo_documento": "COMP_DOMICILIO",
        "documento_obligatorio": True,
        "dias_maximos_vigencia": 90,
    },
    # Misma caducidad estricta para la constancia de situación fiscal: el
    # DOC-02 (Tabla 2) le exige una vigencia «no mayor a 3 meses».
    {
        "codigo_regla": "RCV-03",
        "nombre_regla": "Caducidad Estricta de la Constancia de Situación Fiscal",
        "familia_regla": "RCV",
        "descripcion": (
            "La constancia de situación fiscal debe haberse emitido en los últimos 3 meses (90 días "
            "naturales), conforme al inventario del expediente corporativo del DOC-02. El sistema calcula "
            "la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 90 días, la "
            "constancia se marca como vencida y debe solicitarse una actualizada al portal del SAT. Si el "
            "documento no declara fecha de emisión, el caso se turna a revisión humana."
        ),
        "severidad": "ALTA",
        "accion": (
            "Más de 90 días desde la emisión: constancia vencida, Semáforo Rojo y solicitud de una "
            "constancia actualizada."
        ),
        "tipo_documento": "CSF_SAT",
        "documento_obligatorio": True,
        "dias_maximos_vigencia": 90,
    },
    # Caducidad estricta de la opinión de cumplimiento (PLUS-03). El DOC-05 la
    # pone como ejemplo de la regla: «opiniones de cumplimiento fiscal con
    # vigencia de 30 días naturales a partir de su emisión».
    {
        "codigo_regla": "RCV-04",
        "nombre_regla": "Caducidad Estricta de la Opinión de Cumplimiento (32-D)",
        "familia_regla": "RCV",
        "descripcion": (
            "La opinión de cumplimiento de obligaciones fiscales (artículo 32-D del Código Fiscal de la Federación) "
            "tiene una vigencia de 30 días naturales a partir de su emisión (DOC-05, caducidad estricta). El "
            "sistema calcula la diferencia entre la fecha de evaluación y la fecha de emisión; si supera los 30 "
            "días, la opinión se marca como vencida. Si el documento no declara fecha de emisión, el caso se turna "
            "a revisión humana."
        ),
        "severidad": "ALTA",
        "accion": (
            "Más de 30 días desde la emisión: opinión vencida, Semáforo Rojo y solicitud de una opinión "
            "actualizada al portal del SAT."
        ),
        "tipo_documento": "OPINION_CUMPLIMIENTO",
        "documento_obligatorio": False,
        "dias_maximos_vigencia": 30,
    },
]


# Elementos que el Nivel 4 verifica en el contenido de cada tipo de documento
# (familia RSC). La descripción es el criterio que lee el modelo (RDS-02) y la
# acción, la recomendación si el elemento falta. Se redactan a partir de la
# columna «Criterios de validación» de las Tablas 2 a 4 del DOC-02, de los
# rasgos con que el Cap. I identifica cada documento y de RSC-01 (DOC-05).
# Un elemento faltante deja el dictamen EN_REVISION (semáforo amarillo), nunca
# NO_CONFORME: la omisión la confirma el analista.
_RSC = [
    # Contrato de prestación de servicios — RSC-01 y DOC-02 Tabla 4: «cláusulas
    # obligatorias (objeto, vigencia, penalización, confidencialidad), firmas».
    ("RSC-01-CONT-OBJ", "CONTRATO_SERVICIOS", "Objeto del contrato",
     "El contrato define su objeto: los servicios que se prestan.",
     "Solicitar la versión del contrato que defina con claridad el objeto de los servicios."),
    ("RSC-01-CONT-VIG", "CONTRATO_SERVICIOS", "Vigencia y terminación anticipada",
     "El contrato establece su vigencia o duración y el procedimiento de terminación anticipada o rescisión.",
     "Revisar con el área jurídica la vigencia y la cláusula de rescisión; si faltan, solicitar un convenio "
     "modificatorio que las incorpore."),
    ("RSC-01-CONT-PEN", "CONTRATO_SERVICIOS", "Penalización por incumplimiento",
     "El contrato establece penas convencionales o penalizaciones por incumplimiento.",
     "Omisión contractual relevante: revisar con el área jurídica la inclusión de penas convencionales."),
    ("RSC-01-CONT-CONF", "CONTRATO_SERVICIOS", "Confidencialidad y no divulgación",
     "El contrato incluye una obligación de confidencialidad o de no divulgación entre las partes.",
     "Omisión contractual relevante: incorporar la cláusula de confidencialidad o anexar un acuerdo de "
     "confidencialidad (NDA)."),
    ("RSC-01-CONT-FIRM", "CONTRATO_SERVICIOS", "Firmas de las partes",
     "El contrato identifica a las partes y contiene el apartado de firmas de sus representantes.",
     "Solicitar el ejemplar firmado por todas las partes."),
    # Acuerdo de confidencialidad — DOC-02 Tabla 4: «cláusula de no divulgación,
    # identificación de las partes, vigencia».
    ("RSC-01-NDA-NODIV", "ACUERDO_CONFIDENCIALIDAD", "Cláusula de no divulgación",
     "El acuerdo contiene una cláusula de no divulgación de la información confidencial.",
     "Solicitar la versión del acuerdo que incluya la obligación de no divulgación."),
    ("RSC-01-NDA-PART", "ACUERDO_CONFIDENCIALIDAD", "Identificación de las partes",
     "El acuerdo identifica a las partes que se obligan a la confidencialidad.",
     "Solicitar el acuerdo con la identificación completa de las partes."),
    ("RSC-01-NDA-VIG", "ACUERDO_CONFIDENCIALIDAD", "Vigencia de la confidencialidad",
     "El acuerdo establece la vigencia o duración de la obligación de confidencialidad.",
     "Revisar con el área jurídica la vigencia de la obligación de confidencialidad."),
    # Acta constitutiva — Cap. I: número de escritura o instrumento público, datos
    # del notario o corredor público e inscripción en el Registro Público de
    # Comercio; LGSM (Cap. III): facultades de los representantes.
    ("RSC-ACTA-ESCR", "ACTA_CONSTITUTIVA", "Escritura pública y notario",
     "El acta indica el número de escritura o instrumento público y el notario o corredor público ante quien se "
     "otorgó.",
     "Solicitar la copia certificada completa del acta, en la que consten el número de escritura y los datos del "
     "notario."),
    ("RSC-ACTA-RPC", "ACTA_CONSTITUTIVA", "Inscripción en el Registro Público de Comercio",
     "El acta incluye la constancia o los datos de inscripción en el Registro Público de la Propiedad y del "
     "Comercio (folio mercantil).",
     "Solicitar la boleta o constancia de inscripción en el Registro Público de Comercio."),
    ("RSC-ACTA-ADMON", "ACTA_CONSTITUTIVA", "Administración y facultades de representación",
     "El acta designa al órgano de administración (administrador único o consejo de administración) y señala "
     "quién ejerce la representación legal y con qué facultades.",
     "Verificar en el acta o en un poder notarial vigente quién ejerce la representación legal y con qué "
     "facultades (RN-03)."),
    # Poder notarial — DOC-02 Tabla 4: «emitido por notario público,
    # identificación del otorgante y apoderado»; LGSM: facultades.
    ("RSC-PODER-NOT", "PODER_NOTARIAL", "Otorgamiento ante notario",
     "El poder fue otorgado ante notario público e indica el número de escritura.",
     "Solicitar el testimonio notarial del poder con el número de escritura."),
    ("RSC-PODER-PART", "PODER_NOTARIAL", "Otorgante y apoderado",
     "El poder identifica al otorgante (poderdante) y al apoderado.",
     "Solicitar el poder con la identificación completa del otorgante y del apoderado."),
    ("RSC-PODER-FAC", "PODER_NOTARIAL", "Facultades conferidas",
     "El poder señala las facultades conferidas: pleitos y cobranzas, actos de administración o actos de "
     "dominio.",
     "Verificar que las facultades del apoderado basten para los actos que suscribe (RN-03)."),
    # Póliza de seguro — DOC-02 Tabla 5: «coberturas mínimas requeridas, montos adecuados».
    ("RSC-POL-COB", "POLIZA_SEGURO", "Coberturas y suma asegurada",
     "La póliza especifica las coberturas contratadas y la suma asegurada.",
     "Solicitar la carátula de la póliza con el detalle de coberturas y suma asegurada."),
    # Licencia de operación — DOC-02 Tabla 5: «correspondencia con giro empresarial».
    ("RSC-LIC-GIRO", "LICENCIA_OPERACION", "Giro o actividad autorizada",
     "La licencia indica el giro o la actividad que autoriza a operar.",
     "Verificar que la licencia corresponda al giro empresarial del titular; si no lo indica, solicitar la "
     "licencia completa."),
]
REGLAS_BASE += [
    # Sentido de la opinión 32-D (PLUS-03). Es un hecho declarado por el SAT en
    # un formato fijo: el ai-service lo lee del texto con reglas deterministas
    # (pipelines/opinion_cumplimiento.py), sin consultar al modelo. A diferencia
    # de los demás elementos RSC, un sentido NEGATIVO sí deja el dictamen
    # NO_CONFORME: no es una omisión dudosa, es lo que el documento afirma.
    {
        "codigo_regla": "RSC-OPIN-SENT",
        "nombre_regla": "Sentido positivo de la opinión de cumplimiento",
        "familia_regla": "RSC",
        "descripcion": (
            "La opinión de cumplimiento declara expresamente su sentido. Positivo: el contribuyente está al "
            "corriente de sus obligaciones fiscales. Negativo: el dictamen es NO_CONFORME. Sin obligaciones, no "
            "inscrito o sin sentido legible: revisión humana."
        ),
        "severidad": "ALTA",
        "accion": (
            "Solicitar al titular una opinión de cumplimiento en sentido positivo emitida en los últimos 30 días; "
            "si es negativa, debe regularizar su situación fiscal ante el SAT antes de continuar."
        ),
        "tipo_documento": "OPINION_CUMPLIMIENTO",
        "documento_obligatorio": False,
        "dias_maximos_vigencia": None,
    },
]
REGLAS_BASE += [
    {
        "codigo_regla": codigo,
        "nombre_regla": nombre,
        "familia_regla": "RSC",
        "descripcion": criterio,
        "severidad": "MEDIA_ALTA",
        "accion": recomendacion,
        "tipo_documento": tipo,
        "documento_obligatorio": False,
        "dias_maximos_vigencia": None,
    }
    for codigo, tipo, nombre, criterio, recomendacion in _RSC
]


def precargar_reglas(verboso: bool = True, sincronizar: bool = True) -> int:
    """Inserta las reglas base que falten y devuelve cuántas se agregaron."""
    if verboso:
        print("=" * 60)
        print("Sincronizando tablas y precargando catálogo de reglas (DOC-05)...")
    if sincronizar:
        init_db()

    db = SessionLocal()
    insertadas = 0
    try:
        existentes = {codigo for (codigo,) in db.query(Regla.codigo_regla).all()}
        for datos in REGLAS_BASE:
            if datos["codigo_regla"] in existentes:
                if verboso:
                    print(f"[SKIP] La regla '{datos['codigo_regla']}' ya existe. No se duplica.")
                continue

            db.add(Regla(**datos))
            insertadas += 1
            if verboso:
                print(f"[OK] Regla '{datos['codigo_regla']}' - {datos['nombre_regla']} precargada.")

        db.commit()
        if verboso:
            print("=" * 60)
            print("Precarga de reglas_validacion finalizada con éxito.")
        return insertadas
    finally:
        db.close()


if __name__ == "__main__":
    precargar_reglas()
