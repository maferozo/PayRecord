"""Carga el catálogo de categorías predeterminadas (§8).

Es idempotente: ejecutarlo varias veces no duplica ni pisa lo que el
usuario haya podido ajustar, salvo que se pase --actualizar.

    python manage.py cargar_categorias
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.obligaciones.enums import AmbitoCategoria
from apps.obligaciones.models import Categoria

A = AmbitoCategoria

# codigo, nombre, ambito, peso_prioridad, color, icono
#
# El peso alimenta el algoritmo de prioridades (§12). Las obligaciones cuyo
# incumplimiento tiene consecuencias legales o financieras pesan más.
CATALOGO = [
    # --- Compartidas por los dos tipos de cuenta ---
    ("servicios",        "Servicios",         A.AMBOS,    3, "#0EA5E9", "bi-lightning-charge"),
    ("creditos",         "Créditos",          A.AMBOS,    5, "#DC2626", "bi-bank"),
    ("impuestos",        "Impuestos",         A.AMBOS,    5, "#7C3AED", "bi-file-earmark-text"),
    ("otros",            "Otros",             A.AMBOS,    0, "#6B7280", "bi-three-dots"),

    # --- Solo cuentas personales ---
    ("vivienda",         "Vivienda",          A.PERSONAL, 4, "#F59E0B", "bi-house-door"),
    ("suscripciones",    "Suscripciones",     A.PERSONAL, 1, "#EC4899", "bi-play-circle"),
    ("educacion",        "Educación",         A.PERSONAL, 2, "#2563EB", "bi-mortarboard"),
    ("salud",            "Salud",             A.PERSONAL, 3, "#10B981", "bi-heart-pulse"),

    # --- Solo cuentas de empresa ---
    ("proveedores",      "Proveedores",       A.EMPRESA,  4, "#0891B2", "bi-truck"),
    ("nomina",           "Nómina",            A.EMPRESA,  5, "#DC2626", "bi-people"),
    ("seguridad-social", "Seguridad social",  A.EMPRESA,  5, "#B45309", "bi-shield-plus"),
    ("arriendo",         "Arriendo",          A.EMPRESA,  4, "#F59E0B", "bi-building"),
    ("software",         "Software",          A.EMPRESA,  2, "#6366F1", "bi-window-stack"),
]


class Command(BaseCommand):
    help = "Crea o actualiza las categorías predeterminadas del sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--actualizar",
            action="store_true",
            help="Sobrescribe nombre, ámbito, peso, color e icono de las ya existentes.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        creadas = actualizadas = sin_cambios = 0

        for codigo, nombre, ambito, peso, color, icono in CATALOGO:
            valores = {
                "nombre": nombre,
                "ambito": ambito,
                "peso_prioridad": peso,
                "color": color,
                "icono": icono,
                "usuario": None,
                "activa": True,
            }

            categoria, creada = Categoria.objects.get_or_create(
                codigo=codigo, defaults=valores
            )

            if creada:
                creadas += 1
            elif opciones["actualizar"]:
                for campo, valor in valores.items():
                    setattr(categoria, campo, valor)
                categoria.save()
                actualizadas += 1
            else:
                sin_cambios += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Categorías predeterminadas: {creadas} creadas, "
                f"{actualizadas} actualizadas, {sin_cambios} sin cambios "
                f"({len(CATALOGO)} en el catálogo)."
            )
        )
