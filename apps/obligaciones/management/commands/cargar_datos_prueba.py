"""Datos ficticios para desarrollo y demostración (§37).

    python manage.py cargar_datos_prueba

Crea dos cuentas de ejemplo con obligaciones en los cuatro estados, para
poder ver la aplicación con contenido realista. Es idempotente.

NO ejecutar en producción: las contraseñas son públicas y previsibles.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.obligaciones.models import Categoria, Obligacion
from apps.usuarios.models import Empresa, TipoUsuario

Usuario = get_user_model()

CLAVE = "Demo12345"

# concepto, monto, dias respecto a hoy, codigo de categoria, prioridad, pagada
OBLIGACIONES_PERSONALES = [
    ("Crédito de vivienda", 450000, 1, "creditos", "ALTA", False),
    ("Internet", 120000, 3, "servicios", "MEDIA", False),
    ("Energía", 185000, -4, "servicios", "ALTA", False),
    ("Arriendo", 900000, 6, "vivienda", "ALTA", False),
    ("Netflix", 35900, 10, "suscripciones", "BAJA", False),
    ("Impuesto vehicular", 320000, 45, "impuestos", "MEDIA", False),
    ("Gimnasio", 89000, -12, "salud", "BAJA", True),
    ("Agua", 74500, -20, "servicios", "MEDIA", True),
]

OBLIGACIONES_EMPRESA = [
    ("Proveedor XYZ", 850000, 1, "proveedores", "ALTA", False, "Distribuidora XYZ", "FAC-00123"),
    ("Seguridad social", 1200000, 6, "seguridad-social", "ALTA", False, "", "PILA-0824"),
    ("Nómina quincenal", 4500000, 6, "nomina", "ALTA", False, "", ""),
    ("Arriendo de bodega", 2100000, -3, "arriendo", "ALTA", False, "Inmobiliaria Central", ""),
    ("Licencias de software", 340000, 18, "software", "BAJA", False, "Softline", "SL-9912"),
    ("Internet corporativo", 260000, -25, "servicios", "MEDIA", True, "Claro", ""),
]


class Command(BaseCommand):
    help = "Crea usuarios y obligaciones de ejemplo para desarrollo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra las obligaciones de las cuentas de ejemplo antes de crearlas.",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not Categoria.objects.predeterminadas().exists():
            raise CommandError(
                "No hay categorías cargadas. Ejecuta antes: python manage.py cargar_categorias"
            )

        hoy = timezone.localdate()

        maria = self._usuario_personal()
        gerente = self._usuario_empresa()

        if opciones["limpiar"]:
            borradas = Obligacion.objects.filter(usuario__in=[maria, gerente]).delete()[0]
            self.stdout.write(f"  {borradas} obligación(es) de ejemplo eliminadas.")

        creadas = 0
        for concepto, monto, dias, codigo, prioridad, pagada in OBLIGACIONES_PERSONALES:
            creadas += self._crear(maria, None, concepto, monto, hoy + timedelta(days=dias),
                                   codigo, prioridad, pagada)

        for concepto, monto, dias, codigo, prioridad, pagada, proveedor, referencia in OBLIGACIONES_EMPRESA:
            creadas += self._crear(gerente, gerente.empresa, concepto, monto,
                                   hoy + timedelta(days=dias), codigo, prioridad, pagada,
                                   proveedor, referencia)

        # Reglas de recordatorio para las obligaciones sin pagar (§13).
        from apps.recordatorios.services.generacion import aplicar_reglas

        con_reglas = 0
        for obligacion in Obligacion.objects.filter(
            usuario__in=[maria, gerente], pagada=False, eliminada_en__isnull=True
        ):
            aplicar_reglas(obligacion, [7, 3, 1, 0])
            con_reglas += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDatos de prueba listos: {creadas} obligación(es) creadas, "
            f"{con_reglas} con recordatorios configurados.\n"
            f"  Cuenta personal: maria@example.com / {CLAVE}\n"
            f"  Cuenta empresa:  gerente@comercialxyz.com / {CLAVE}\n"
        ))

    def _usuario_personal(self):
        usuario, creado = Usuario.objects.get_or_create(
            email="maria@example.com",
            defaults={"nombre": "María Rodríguez", "tipo_usuario": TipoUsuario.PERSONAL},
        )
        if creado:
            usuario.set_password(CLAVE)
            usuario.save()
            self.stdout.write("  Usuario personal creado: maria@example.com")
        return usuario

    def _usuario_empresa(self):
        empresa, _ = Empresa.objects.get_or_create(
            nit="900123456-7",
            defaults={"nombre": "Comercial XYZ S.A.S.", "telefono": "6041234567"},
        )
        usuario, creado = Usuario.objects.get_or_create(
            email="gerente@comercialxyz.com",
            defaults={
                "nombre": "Carlos Gómez",
                "tipo_usuario": TipoUsuario.EMPRESA,
                "empresa": empresa,
            },
        )
        if creado:
            usuario.set_password(CLAVE)
            usuario.save()
            self.stdout.write("  Usuario empresa creado: gerente@comercialxyz.com")
        return usuario

    def _crear(self, usuario, empresa, concepto, monto, fecha, codigo, prioridad,
               pagada, proveedor="", referencia=""):
        categoria = Categoria.objects.get(codigo=codigo)
        _, creada = Obligacion.objects.get_or_create(
            usuario=usuario,
            concepto=concepto,
            defaults={
                "empresa": empresa,
                "monto": Decimal(monto),
                "fecha_vencimiento": fecha,
                "categoria": categoria,
                "prioridad_usuario": prioridad,
                "pagada": pagada,
                "fecha_pago": fecha if pagada else None,
                "proveedor": proveedor,
                "referencia": referencia,
            },
        )
        return 1 if creada else 0
