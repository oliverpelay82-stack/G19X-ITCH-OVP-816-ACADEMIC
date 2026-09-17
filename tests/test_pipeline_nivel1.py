"""
Prueba unitaria / integración rápida para verificar:
1. Rechazo de tipo de documento no permitido (Enum validation).
2. Rechazo de archivo corrupto o con extensión falsa (Magic bytes validation).
3. Aceptación de archivo PDF válido con cálculo inmutable SHA-256.
4. Cálculo correcto de completitud por tipos distintos (no conteo ciego).
5. Transición de estado del expediente a CONFORME al completar los 3 obligatorios.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from main import app
from config.database import SessionLocal
from models.titular import TitularExpediente
from models.expediente import Expediente
from models.documento import Documento

client = TestClient(app)

def run_tests():
    print("=== INICIANDO PRUEBAS DEL PIPELINE DE VALIDACIÓN (NIVEL 1 & 2 BASE) ===")
    
    # 1. Obtener o crear un expediente de prueba
    db = SessionLocal()
    expediente = db.query(Expediente).first()
    if not expediente:
        titular = TitularExpediente(
            rfc="PRU010101XYZ",
            razon_social="Empresa de Pruebas Unitarias S.A. de C.V.",
            tipo_persona="MORAL",
            categoria="PROVEEDOR"
        )
        db.add(titular)
        db.commit()
        db.refresh(titular)
        
        expediente = Expediente(
            titular_id=titular.id,
            codigo_expediente="EXP-TEST-001",
            estado_cumplimiento="EN_REVISION",
            porcentaje_completitud=0.0
        )
        db.add(expediente)
        db.commit()
        db.refresh(expediente)
    
    exp_id = expediente.id
    print(f"[*] Usando expediente: {expediente.codigo_expediente} (ID: {exp_id})")

    # Limpiar documentos previos de este expediente para prueba determinista limpia
    db.query(Documento).filter(Documento.expediente_id == exp_id).delete()
    expediente.porcentaje_completitud = 0.0
    expediente.estado_cumplimiento = "EN_REVISION"
    db.commit()
    db.close()

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

    db.close()
    print("\n=== TODAS LAS PRUEBAS DEL PIPELINE PASARON SATISFACTORIAMENTE ===")

if __name__ == "__main__":
    run_tests()
