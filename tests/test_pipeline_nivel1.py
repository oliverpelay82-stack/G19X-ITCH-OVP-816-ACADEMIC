"""
Prueba unitaria / integración rápida para verificar:
1. Rechazo de tipo de documento no permitido (Enum validation).
2. Rechazo de archivo corrupto o con extensión falsa (Magic bytes validation).
3. Aceptación de archivo PDF válido con cálculo inmutable SHA-256.
4. Cálculo correcto de completitud por tipos distintos (no conteo ciego).
5. Transición de estado del expediente a CONFORME al completar los 3 obligatorios.

Aislamiento: la prueba crea su propio titular y expediente temporales
(EXP-TEST-TMP) y, al terminar —pase o falle—, borra únicamente lo que ella
misma creó. Nunca lee ni modifica los expedientes reales de la base de datos.
Los binarios de prueba solo se eliminan de la bóveda si ningún otro registro
los referencia (dos archivos idénticos comparten el mismo nombre en la bóveda).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "core-service")))

from fastapi.testclient import TestClient
from main import app
from config.database import SessionLocal
from models.titular import TitularExpediente
from models.expediente import Expediente
from models.documento import Documento

client = TestClient(app)

CODIGO_EXPEDIENTE_TMP = "EXP-TEST-TMP"
RFC_TITULAR_TMP = "TMP010101AAA"


def _limpiar_entidades_temporales() -> None:
    """
    Elimina el expediente y el titular temporales, sus documentos y los
    binarios de bóveda que solo ellos usaban. Filtra siempre por el código o
    RFC temporales: jamás toca un registro que la prueba no haya creado.
    """
    db = SessionLocal()
    try:
        titular = db.query(TitularExpediente).filter(TitularExpediente.rfc == RFC_TITULAR_TMP).first()
        expediente = db.query(Expediente).filter(Expediente.codigo_expediente == CODIGO_EXPEDIENTE_TMP).first()

        if expediente:
            documentos = db.query(Documento).filter(Documento.expediente_id == expediente.id).all()
            rutas = {d.ruta_almacenamiento for d in documentos}
            for documento in documentos:
                db.delete(documento)
            db.flush()
            for ruta in rutas:
                compartida = db.query(Documento).filter(Documento.ruta_almacenamiento == ruta).first()
                if not compartida and os.path.isfile(ruta):
                    os.remove(ruta)
            db.delete(expediente)
        if titular:
            db.flush()
            db.delete(titular)
        db.commit()
    finally:
        db.close()


def _crear_expediente_temporal() -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(
            rfc=RFC_TITULAR_TMP,
            razon_social="Titular Temporal de Pruebas Automatizadas S.A. de C.V.",
            tipo_persona="MORAL",
            categoria="PROVEEDOR",
        )
        db.add(titular)
        db.flush()
        expediente = Expediente(
            titular_id=titular.id,
            codigo_expediente=CODIGO_EXPEDIENTE_TMP,
            estado_cumplimiento="EN_REVISION",
            porcentaje_completitud=0.0,
        )
        db.add(expediente)
        db.commit()
        return expediente.id
    finally:
        db.close()


def run_tests():
    print("=== INICIANDO PRUEBAS DEL PIPELINE DE VALIDACIÓN (NIVEL 1 & 2 BASE) ===")

    # Restos de una ejecución anterior interrumpida.
    _limpiar_entidades_temporales()
    exp_id = _crear_expediente_temporal()
    print(f"[*] Usando expediente temporal: {CODIGO_EXPEDIENTE_TMP} (ID: {exp_id})")

    try:
        _ejecutar_casos(exp_id)
    finally:
        _limpiar_entidades_temporales()
        print(f"[*] Expediente temporal {CODIGO_EXPEDIENTE_TMP} eliminado junto con sus documentos.")

    print("\n=== TODAS LAS PRUEBAS DEL PIPELINE PASARON SATISFACTORIAMENTE ===")


def _ejecutar_casos(exp_id: str) -> None:
    # TEST 1: Rechazo de tipo documental no registrado en el catálogo
    print("\n[TEST 1] Probando envío de tipo de documento no admitido ('TIPO_FALSO')...")
    res1 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "TIPO_FALSO"},
        files={"file": ("test.pdf", b"%PDF-1.4 Fake PDF Content", "application/pdf")}
    )
    assert res1.status_code == 422, f"Esperaba 422, obtuve {res1.status_code}: {res1.text}"
    print(" -> PASÓ: Rechazado exitosamente con HTTP 422 (Catálogo oficial protegido).")

    # TEST 2: Rechazo de archivo corrupto / extensión falsa (Magic bytes)
    print("\n[TEST 2] Probando archivo falso (archivo de texto renombrado a .pdf sin cabecera %PDF-)...")
    res2 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
        files={"file": ("malicioso.pdf", b"Este es un texto plano sin firma PDF", "application/pdf")}
    )
    assert res2.status_code == 400, f"Esperaba 400, obtuve {res2.status_code}: {res2.text}"
    print(f" -> PASÓ: Rechazado exitosamente con HTTP 400 ({res2.json()['detail']}).")

    # TEST 3: Carga de 1er documento obligatorio (CSF_SAT) válido
    print("\n[TEST 3] Subiendo documento válido 1/3 (CSF_SAT con firma %PDF-)...")
    res3 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
        files={"file": ("csf_sat.pdf", b"%PDF-1.4 Contenido Fiscal Autentico", "application/pdf")}
    )
    assert res3.status_code == 201, f"Esperaba 201, obtuve {res3.status_code}: {res3.text}"
    doc1 = res3.json()
    print(f" -> PASÓ: Aceptado con SHA-256: {doc1['hash_sha256'][:16]}...")

    # Verificar que completitud es 33.3%
    exp_data = client.get(f"/api/v1/expedientes/{exp_id}").json()
    print(f" -> Completitud actual: {exp_data['porcentaje_completitud']}%, Estado: {exp_data['estado_cumplimiento']}")
    assert float(exp_data['porcentaje_completitud']) == 33.3

    # TEST 4: Subir otra vez CSF_SAT (tipo repetido) NO debe sumar porcentaje
    print("\n[TEST 4] Subiendo segundo documento pero con el MISMO tipo (CSF_SAT repetido)...")
    res4 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
        files={"file": ("csf_sat_v2.pdf", b"%PDF-1.4 Segunda version del mismo tipo", "application/pdf")}
    )
    assert res4.status_code == 201
    exp_data = client.get(f"/api/v1/expedientes/{exp_id}").json()
    print(f" -> Completitud tras tipo repetido: {exp_data['porcentaje_completitud']}%")
    assert float(exp_data['porcentaje_completitud']) == 33.3, f"No debía subir de 33.3%, subió a {exp_data['porcentaje_completitud']}%"
    print(" -> PASÓ: No hubo conteo ciego, el porcentaje no aumentó indebidamente.")

    # TEST 5: Carga del 2do documento obligatorio (COMP_DOMICILIO)
    print("\n[TEST 5] Subiendo documento obligatorio 2/3 (COMP_DOMICILIO)...")
    res5 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "COMP_DOMICILIO"},
        files={"file": ("comprobante_cfe.pdf", b"%PDF-1.4 Recibo CFE Domicilio Fiscal", "application/pdf")}
    )
    assert res5.status_code == 201
    exp_data = client.get(f"/api/v1/expedientes/{exp_id}").json()
    print(f" -> Completitud actual: {exp_data['porcentaje_completitud']}%, Estado: {exp_data['estado_cumplimiento']}")
    assert float(exp_data['porcentaje_completitud']) == 66.7

    # TEST 6: Carga del 3er documento obligatorio (ACTA_CONSTITUTIVA)
    print("\n[TEST 6] Subiendo documento obligatorio 3/3 (ACTA_CONSTITUTIVA)...")
    res6 = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": "ACTA_CONSTITUTIVA"},
        files={"file": ("acta_constitutiva.pdf", b"%PDF-1.4 Escritura Publica Notarial", "application/pdf")}
    )
    assert res6.status_code == 201
    exp_data = client.get(f"/api/v1/expedientes/{exp_id}").json()
    print(f" -> Completitud actual: {exp_data['porcentaje_completitud']}%, Estado: {exp_data['estado_cumplimiento']}")
    assert float(exp_data['porcentaje_completitud']) == 100.0
    assert exp_data['estado_cumplimiento'] == "CONFORME"
    print(" -> PASÓ: El expediente alcanzó el 100.0% y cambió automáticamente su estado a CONFORME!")


if __name__ == "__main__":
    run_tests()
