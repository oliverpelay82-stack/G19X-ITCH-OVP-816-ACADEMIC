"""
Crea un titular y expediente de demostración si la tabla está vacía.
Ejecuta (desde services/core-service/): python seed_demo.py
"""
from config.database import SessionLocal, init_db
from models.titular import TitularExpediente
from models.expediente import Expediente


def seed_demo():
    init_db()
    db = SessionLocal()
    try:
        titular_existente = db.query(TitularExpediente).first()
        if not titular_existente:
            titular = TitularExpediente(
                rfc="BIM980101XYZ",
                razon_social="GRUPO BIMBO S.A.B. DE C.V.",
                tipo_persona="MORAL",
                categoria="PROVEEDOR_CRITICO",
            )
            db.add(titular)
            db.flush()

            expediente = Expediente(
                titular_id=titular.id,
                codigo_expediente=f"EXP-{titular.rfc}-001",
                estado_cumplimiento="EN_REVISION",
                porcentaje_completitud=0.0,
            )
            db.add(expediente)
            db.commit()
            print(
                f"[+] Titular y Expediente demo inicial creados: "
                f"{titular.razon_social} ({expediente.codigo_expediente})"
            )
        else:
            print("[i] Ya existen titulares en la base de datos.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
