from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Categoria
from .models import Producto, ProductoGrupoOpcion

def bienvenida(request):
    return render(request, 'index.html')

def menu(request):
    categorias = Categoria.objects.all()
    contexto = {
        'categorias': categorias
    }
    return render(request, 'menu.html', contexto)

def detalleProducto(request, idproducto):

    
    producto = get_object_or_404(Producto, pk=idproducto)
    
    relaciones_grupos = ProductoGrupoOpcion.objects.filter(idproducto=producto)
    grupos_opciones = []
    for rel in relaciones_grupos:
        grupo = rel.idgrupo
        opciones = grupo.opcion_set.all()
        grupos_opciones.append({
            'grupo': grupo,
            'opciones': opciones
        })

    contexto = {
        'producto': producto,
        'grupos_opciones': grupos_opciones
    }
    # Apuntamos al archivo con el nombre exacto
    return render(request, 'detalleProducto.html', contexto)