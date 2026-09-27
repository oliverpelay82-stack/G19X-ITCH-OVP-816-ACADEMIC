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
prestación de servicios (RIE-02, RF-07).

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
]


def precargar_reglas():
    print("=" * 60)
    print("Sincronizando tablas y precargando catálogo de reglas (DOC-05)...")
    init_db()

    db = SessionLocal()
    try:
        for datos in REGLAS_BASE:
            existente = db.query(Regla).filter(Regla.codigo_regla == datos["codigo_regla"]).first()
            if existente:
                print(f"[SKIP] La regla '{datos['codigo_regla']}' ya existe. No se duplica.")
                continue

            nueva_regla = Regla(**datos)
            db.add(nueva_regla)
            print(f"[OK] Regla '{datos['codigo_regla']}' - {datos['nombre_regla']} precargada.")

        db.commit()
        print("=" * 60)
        print("Precarga de reglas_validacion finalizada con éxito.")
    finally:
        db.close()


if __name__ == "__main__":
    precargar_reglas()
