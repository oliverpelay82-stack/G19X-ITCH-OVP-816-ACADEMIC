"""
Servidor SMTP en memoria para las pruebas del correo (RF-20).

``smtpd`` salió de la biblioteca estándar en Python 3.12 y ``aiosmtpd`` sería una
dependencia más solo para pruebas: este servidor atiende el subconjunto de RFC 5321
que usa ``smtplib`` (EHLO/HELO, MAIL, RCPT, DATA, RSET, NOOP, QUIT), sin STARTTLS
ni autenticación, en 127.0.0.1 y un puerto libre. Guarda cada mensaje aceptado y
puede rechazar los destinatarios (``rechazar = True``) para probar un envío fallido.
"""
from __future__ import annotations

import socketserver
import threading
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage


@dataclass
class MensajeRecibido:
    remitente: str
    destinatarios: list[str]
    mensaje: EmailMessage


class _Manejador(socketserver.StreamRequestHandler):
    server: "ServidorSmtp"

    def _responder(self, linea: str) -> None:
        self.wfile.write(f"{linea}\r\n".encode())

    def handle(self) -> None:
        self._responder("220 pruebas ESMTP")
        remitente, destinatarios = "", []
        while True:
            crudo = self.rfile.readline()
            if not crudo:
                return
            linea = crudo.decode(errors="replace").rstrip("\r\n")
            orden = linea[:4].upper()
            if orden == "EHLO":
                self._responder("250-pruebas")
                self._responder("250 8BITMIME")
            elif orden == "HELO":
                self._responder("250 pruebas")
            elif orden == "MAIL":
                remitente, destinatarios = linea.split(":", 1)[1].strip().strip("<>"), []
                self._responder("250 OK")
            elif orden == "RCPT":
                if self.server.rechazar:
                    self._responder("550 Buzon no disponible")
                else:
                    destinatarios.append(linea.split(":", 1)[1].strip().strip("<>"))
                    self._responder("250 OK")
            elif orden == "DATA":
                self._responder("354 Fin con <CRLF>.<CRLF>")
                datos = bytearray()
                while True:
                    renglon = self.rfile.readline()
                    if renglon in (b".\r\n", b".\n", b""):
                        break
                    datos += renglon[1:] if renglon.startswith(b"..") else renglon
                self.server.registrar(MensajeRecibido(
                    remitente, list(destinatarios), message_from_bytes(bytes(datos), policy=policy.default)))
                self._responder("250 OK")
            elif orden == "RSET":
                remitente, destinatarios = "", []
                self._responder("250 OK")
            elif orden == "NOOP":
                self._responder("250 OK")
            elif orden == "QUIT":
                self._responder("221 Adios")
                return
            else:
                self._responder("502 No implementado")


class ServidorSmtp(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Manejador)
        self.recibidos: list[MensajeRecibido] = []
        self.rechazar = False
        self._candado = threading.Lock()
        self._hilo = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def puerto(self) -> int:
        return self.server_address[1]

    def registrar(self, mensaje: MensajeRecibido) -> None:
        with self._candado:
            self.recibidos.append(mensaje)

    def iniciar(self) -> "ServidorSmtp":
        self._hilo.start()
        return self

    def detener(self) -> None:
        self.shutdown()
        self.server_close()
