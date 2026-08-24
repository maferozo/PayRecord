from django.urls import path

from . import views

app_name = "obligaciones"

urlpatterns = [
    # --- Categorías ---
    path("categorias/", views.CategoriaListView.as_view(), name="categoria_lista"),
    path("categorias/nueva/", views.CategoriaCreateView.as_view(), name="categoria_crear"),
    path("categorias/<int:pk>/editar/", views.CategoriaUpdateView.as_view(), name="categoria_editar"),
    path("categorias/<int:pk>/eliminar/", views.CategoriaDeleteView.as_view(), name="categoria_eliminar"),

    # --- Obligaciones ---
    path("obligaciones/", views.ObligacionListView.as_view(), name="lista"),
    path("obligaciones/nueva/", views.ObligacionCreateView.as_view(), name="crear"),
    path("obligaciones/<int:pk>/", views.ObligacionDetailView.as_view(), name="detalle"),
    path("obligaciones/<int:pk>/editar/", views.ObligacionUpdateView.as_view(), name="editar"),
    path("obligaciones/<int:pk>/eliminar/", views.ObligacionDeleteView.as_view(), name="eliminar"),
    path("obligaciones/<int:pk>/pago/", views.CambiarEstadoPagoView.as_view(), name="cambiar_pago"),
]
