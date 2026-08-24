from django.urls import path

from . import views

app_name = "obligaciones"

urlpatterns = [
    path("categorias/", views.CategoriaListView.as_view(), name="categoria_lista"),
    path("categorias/nueva/", views.CategoriaCreateView.as_view(), name="categoria_crear"),
    path("categorias/<int:pk>/editar/", views.CategoriaUpdateView.as_view(), name="categoria_editar"),
    path("categorias/<int:pk>/eliminar/", views.CategoriaDeleteView.as_view(), name="categoria_eliminar"),
]
