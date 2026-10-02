"""Genera los próximos meses de las obligaciones mensuales.

    python manage.py generar_obligaciones_recurrentes
    python manage.py generar_obligaciones_recurrentes --fecha 2026-10-01   # simular un día

Pensado para ejecutarse junto con `generar_recordatorios`. Es idempotente:
ejecutarlo varias veces no crea periodos duplicados.
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.obligaciones.services.recurrencia import generar


class Command(BaseCommand):
    help = "Crea los siguientes periodos de las obligaciones mensuales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fecha",
            help="Fecha a simular en formato AAAA-MM-DD. Por defecto, hoy.",
        )

    def handle(self, *args, **opciones):
        fecha = None
        if opciones["fecha"]:
            try:
                fecha = datetime.strptime(opciones["fecha"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("La fecha debe tener el formato AAAA-MM-DD.")

        creados = generar(hoy=fecha)
        self.stdout.write(self.style.SUCCESS(f"{creados} periodo(s) de obligación creados."))
