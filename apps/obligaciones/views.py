from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .enums import EstadoObligacion
from .forms import CategoriaForm, FiltroObligacionesForm, ObligacionForm
from .models import Categoria, Obligacion


# ===========================================================
#  Categorías
# ===========================================================

class CategoriaListView(LoginRequiredMixin, ListView):
    """Catálogo visible: predeterminadas del ámbito del usuario más las suyas."""

    model = Categoria
    template_name = "obligaciones/categoria_lista.html"
    context_object_name = "categorias"

    def get_queryset(self):
        return Categoria.objects.disponibles_para(self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        categorias = contexto["categorias"]
        contexto["predeterminadas"] = [c for c in categorias if c.es_predeterminada]
        contexto["propias"] = [c for c in categorias if not c.es_predeterminada]
        return contexto


class CategoriaCreateView(LoginRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "obligaciones/categoria_form.html"
    success_url = reverse_lazy("obligaciones:categoria_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f'Categoría "{form.cleaned_data["nombre"]}" creada.')
        return super().form_valid(form)


class CategoriaUpdateView(LoginRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = "obligaciones/categoria_form.html"
    success_url = reverse_lazy("obligaciones:categoria_lista")

    def get_queryset(self):
        # Solo las propias: una predeterminada o la de otro usuario da 404.
        return Categoria.objects.editables_por(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Categoría actualizada.")
        return super().form_valid(form)


class CategoriaDeleteView(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = "obligaciones/categoria_confirmar_borrado.html"
    success_url = reverse_lazy("obligaciones:categoria_lista")

    def get_queryset(self):
        return Categoria.objects.editables_por(self.request.user)

    def form_valid(self, form):
        """Una categoría con obligaciones no se borra: se desactiva.

        Obligacion.categoria usa on_delete=PROTECT, así que la base de datos
        impide el borrado y aquí se convierte en desactivación para no romper
        el historial ni las estadísticas.
        """
        categoria = self.get_object()
        try:
            return super().form_valid(form)
        except ProtectedError:
            categoria.activa = False
            categoria.save()
            messages.warning(
                self.request,
                f'"{categoria.nombre}" tiene obligaciones asociadas, así que se '
                "desactivó en lugar de borrarse. Tu historial queda intacto.",
            )
            return redirect(self.success_url)


# ===========================================================
#  Obligaciones
# ===========================================================

class ObligacionQuerysetMixin(LoginRequiredMixin):
    """Toda vista de obligaciones parte de aquí.

    Garantiza que ninguna consulta escape del filtro de propiedad (§28).
    """

    model = Obligacion

    def get_queryset(self):
        return Obligacion.objects.para_usuario(self.request.user).select_related(
            "categoria", "empresa"
        )


class ObligacionListView(ObligacionQuerysetMixin, ListView):
    """Mis obligaciones, con filtros (§17)."""

    template_name = "obligaciones/obligacion_lista.html"
    context_object_name = "obligaciones"
    paginate_by = 20

    def get_queryset(self):
        consulta = super().get_queryset()
        self.filtros = FiltroObligacionesForm(
            self.request.GET or None, usuario=self.request.user
        )

        if self.filtros.is_valid():
            datos = self.filtros.cleaned_data
            consulta = consulta.buscar(datos.get("q"))

            if datos.get("estado"):
                consulta = consulta.en_estado(datos["estado"])
            if datos.get("categoria"):
                consulta = consulta.filter(categoria=datos["categoria"])
            if datos.get("prioridad"):
                consulta = consulta.filter(prioridad_usuario=datos["prioridad"])

        return consulta.order_by("pagada", "fecha_vencimiento", "-monto")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["filtros"] = self.filtros

        # Totales del conjunto filtrado, no solo de la página visible.
        consulta = self.get_queryset()
        contexto["total_pendiente"] = (
            consulta.pendientes_de_pago().aggregate(t=Sum("monto"))["t"] or 0
        )
        contexto["conteo_total"] = consulta.count()
        return contexto


class ObligacionDetailView(ObligacionQuerysetMixin, DetailView):
    template_name = "obligaciones/obligacion_detalle.html"
    context_object_name = "obligacion"


class ObligacionCreateView(LoginRequiredMixin, CreateView):
    model = Obligacion
    form_class = ObligacionForm
    template_name = "obligaciones/obligacion_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f'Obligación "{self.object.concepto}" registrada.')
        return respuesta

    def get_success_url(self):
        return reverse("obligaciones:detalle", args=[self.object.pk])


class ObligacionUpdateView(ObligacionQuerysetMixin, UpdateView):
    form_class = ObligacionForm
    template_name = "obligaciones/obligacion_form.html"

    def get_queryset(self):
        # Sin select_related: UpdateView necesita la instancia editable.
        return Obligacion.objects.visibles_para(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Obligación actualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("obligaciones:detalle", args=[self.object.pk])


class ObligacionDeleteView(ObligacionQuerysetMixin, DeleteView):
    template_name = "obligaciones/obligacion_confirmar_borrado.html"
    context_object_name = "obligacion"
    success_url = reverse_lazy("obligaciones:lista")

    def get_queryset(self):
        return Obligacion.objects.visibles_para(self.request.user)

    def form_valid(self, form):
        """Borrado lógico: la fila se conserva para el historial (decisión D7)."""
        obligacion = self.get_object()
        obligacion.eliminar_logicamente()
        messages.success(self.request, f'"{obligacion.concepto}" eliminada.')
        return HttpResponseRedirect(self.success_url)


class CambiarEstadoPagoView(LoginRequiredMixin, View):
    """Marca como pagada o devuelve a pendiente (§32).

    Solo por POST: cambia datos, así que un GET no debe poder provocarlo.
    """

    def post(self, request, pk):
        obligacion = get_object_or_404(
            Obligacion.objects.visibles_para(request.user), pk=pk
        )

        if obligacion.pagada:
            obligacion.marcar_pendiente()
            messages.info(request, f'"{obligacion.concepto}" vuelve a estar pendiente.')
        else:
            obligacion.marcar_pagada()
            messages.success(request, f'"{obligacion.concepto}" marcada como pagada.')

        destino = request.POST.get("siguiente") or reverse(
            "obligaciones:detalle", args=[obligacion.pk]
        )
        return redirect(destino)
