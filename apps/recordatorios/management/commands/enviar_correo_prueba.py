"""Envía un único correo de prueba, sin tocar obligaciones ni recordatorios
reales -- solo para confirmar que la configuración SMTP funciona.

    python manage.py enviar_correo_prueba tu-correo@gmail.com

No marca nada como "enviado" en la base de datos: no hay nada que marcar,
este comando no crea ningún Recordatorio. Distingue tres situaciones
distintas, que son fáciles de confundir:

    1. El mensaje se armó y se pidió el envío (esto siempre "funciona").
    2. El proveedor SMTP lo aceptó (lo que este comando confirma).
    3. El mensaje llegó de verdad a la bandeja (eso solo lo confirmas tú,
       revisando tu correo -- incluida la carpeta de spam).
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba a una sola dirección, para verificar la configuración SMTP."

    def add_arguments(self, parser):
        parser.add_argument("destino", help="Dirección de correo que va a recibir la prueba.")

    def handle(self, *args, **opciones):
        destino = opciones["destino"]
        backend = settings.EMAIL_BACKEND

        self.stdout.write(f"Backend configurado: {backend}")
        if backend == "django.core.mail.backends.console.EmailBackend":
            self.stdout.write(self.style.WARNING(
                "Backend de consola: el correo se va a imprimir aquí abajo, "
                "no se va a enviar de verdad. Cambia EMAIL_BACKEND en tu "
                ".env si quieres probar el envío real."
            ))

        self.stdout.write("Solicitando el envío...")

        try:
            entregados = send_mail(
                subject="PayRecord — correo de prueba",
                message=(
                    "Si estás leyendo esto en tu bandeja de entrada, la "
                    "configuración SMTP de PayRecord funciona correctamente.\n\n"
                    "Este correo no está asociado a ninguna obligación real."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destino],
                fail_silently=False,
            )
        except Exception as error:
            # El motivo exacto (usuario/contraseña rechazados, host
            # inalcanzable, etc.) lo trae el propio error de smtplib; no hay
            # ningún secreto en ese texto, solo el diagnóstico del servidor.
            raise CommandError(
                f"El proveedor de correo rechazó el envío: {error}"
            ) from error

        if entregados != 1:
            raise CommandError(
                f"El proveedor no confirmó el envío (respuesta: {entregados})."
            )

        self.stdout.write(self.style.SUCCESS(
            f"Aceptado por el proveedor SMTP para {destino}."
        ))
        if backend != "django.core.mail.backends.console.EmailBackend":
            self.stdout.write(
                "Esto NO confirma que haya llegado a la bandeja todavía -- "
                "revisa tu correo (y la carpeta de spam) para confirmarlo."
            )
