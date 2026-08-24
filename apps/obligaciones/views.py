from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import CategoriaForm
from .models import Categoria


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

        El modelo Obligacion (Fase 4) usa on_delete=PROTECT, así que la base
        de datos impide el borrado y aquí se convierte en desactivación para
        no romper el historial ni las estadísticas.
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
