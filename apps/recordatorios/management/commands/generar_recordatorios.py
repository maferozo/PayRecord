"""Proceso automático de recordatorios (§15, §16).

    python manage.py generar_recordatorios
    python manage.py generar_recordatorios --fecha 2026-08-25   # simular un día

Pensado para ejecutarse a diario desde el Programador de tareas de Windows.
Es idempotente, así que no pasa nada si se ejecuta varias veces el mismo día.
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.recordatorios.services.generacion import procesar


class Command(BaseCommand):
    help = "Genera y envía los recordatorios que correspondan a la fecha indicada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fecha",
            help="Fecha a simular en formato AAAA-MM-DD. Por defecto, hoy.",
        )
        parser.add_argument(
            "--solo-generar",
            action="store_true",
            help="Crea los recordatorios pero no los entrega.",
        )

    def handle(self, *args, **opciones):
        fecha = None
        if opciones["fecha"]:
            try:
                fecha = datetime.strptime(opciones["fecha"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("La fecha debe tener el formato AAAA-MM-DD.")

        if opciones["solo_generar"]:
            from apps.recordatorios.services.generacion import generar

            creados = generar(hoy=fecha)
            self.stdout.write(self.style.SUCCESS(f"{creados} recordatorio(s) creados."))
            return

        resultado = procesar(hoy=fecha)

        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {resultado['creados']} creados, "
            f"{resultado['enviados']} enviados, {resultado['errores']} con error."
        ))
