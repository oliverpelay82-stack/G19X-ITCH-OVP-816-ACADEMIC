"""
PLUS-17 (PRD §21.6) — Código QR de verificación del SAT.

La constancia de situación fiscal, la opinión 32-D y la cédula del RFC traen un
QR que lleva a su validación en el portal del SAT. Al auditarlas, se busca el
QR en la primera y la última página (detector de OpenCV, ya instalado), se
guarda el enlace, se comprueba que lleve a un dominio ``sat.gob.mx`` y se
coteja el RFC del enlace con el de referencia (el del titular o, sin él, el del
documento).

**El motor no consulta al SAT:** no hay llamada automática a un servicio
externo; el analista recibe el enlace oficial para validarlo en el portal. Un
QR ausente o ilegible solo se informa (un escaneo puede perderlo).
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import cv2
import fitz  # PyMuPDF
import numpy as np

TIPOS_CON_QR = frozenset({"CSF_SAT", "OPINION_CUMPLIMIENTO", "CEDULA_RFC"})
DPI_QR = 200
_RFC = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z\d]{3}")


def _paginas(documento: fitz.Document) -> list[int]:
    return sorted({0, documento.page_count - 1}) if documento.page_count else []


def _decodificar(pagina: fitz.Page) -> list[str]:
    pixeles = pagina.get_pixmap(matrix=fitz.Matrix(DPI_QR / 72, DPI_QR / 72), colorspace=fitz.csGRAY)
    imagen = np.frombuffer(pixeles.samples, dtype=np.uint8).reshape(pixeles.height, pixeles.width)
    detector = cv2.QRCodeDetector()
    try:
        ok, textos, *_ = detector.detectAndDecodeMulti(imagen)
    except cv2.error:
        return []
    return [t for t in (textos if ok else []) if t]


def _es_sat(url: str) -> tuple[bool, str | None]:
    anfitrion = (urlparse(url).hostname or "").lower() if url.lower().startswith(("http://", "https://")) else ""
    return (anfitrion == "sat.gob.mx" or anfitrion.endswith(".sat.gob.mx")), (anfitrion or None)


def leer(contenido: bytes, rfc_referencia: str | None) -> dict[str, Any]:
    """Resultado de la lectura del QR; ``encontrado`` es False si no hay QR legible en las páginas revisadas."""
    try:
        documento = fitz.open(stream=contenido, filetype="pdf")
    except Exception:  # noqa: BLE001 — un archivo que no abre lo reporta el Nivel 3
        return {"encontrado": False, "paginas_revisadas": []}
    with documento:
        paginas = _paginas(documento)
        for numero in paginas:
            for texto in _decodificar(documento[numero]):
                dominio_sat, anfitrion = _es_sat(texto)
                encontrado = _RFC.search(texto.upper())
                rfc_qr = encontrado.group(0) if encontrado else None
                referencia = (rfc_referencia or "").strip().upper() or None
                return {
                    "encontrado": True,
                    "pagina": numero + 1,
                    "url": texto[:500] if dominio_sat else None,
                    "contenido": None if dominio_sat else texto[:200],
                    "dominio": anfitrion,
                    "dominio_sat": dominio_sat,
                    "rfc_qr": rfc_qr,
                    "rfc_referencia": referencia,
                    "coincide_rfc": (rfc_qr == referencia) if (rfc_qr and referencia) else None,
                    "paginas_revisadas": [p + 1 for p in paginas],
                }
    return {"encontrado": False, "paginas_revisadas": [p + 1 for p in paginas]}


def motivos(qr: dict[str, Any] | None) -> list[str]:
    """Motivos por los que el QR deja la auditoría en revisión humana."""
    if not qr or not qr.get("encontrado"):
        return []
    if not qr.get("dominio_sat"):
        return [f"El código QR del documento no lleva al portal del SAT ({qr.get('dominio') or 'no es un enlace'})."]
    if qr.get("coincide_rfc") is False:
        return [f"El RFC del código QR ({qr['rfc_qr']}) no coincide con el de referencia ({qr['rfc_referencia']})."]
    return []
