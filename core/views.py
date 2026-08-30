from django.shortcuts import render, get_object_or_404, redirect
from .models import Categoria, Producto, ProductoGrupoOpcion, Cliente, Direccion, MedioPago, Pedido, EstadoPedido, Negocio, ZonasEntrega, RedesSociales, Horario

def index(request):
    negocio = Negocio.objects.first()
    horarios = Horario.objects.filter(idnegocio=negocio) if negocio else []
    zonas = ZonasEntrega.objects.filter(idnegocio=negocio) if negocio else []
    
    instagram = RedesSociales.objects.filter(plataforma__icontains='instagram').first()

    context = {
        'negocio': negocio,
        'horarios': horarios,
        'zonas': zonas,
        'instagram': instagram,
    }
    return render(request, 'index.html', context)

def menu(request):
    categorias = Categoria.objects.all()
    
    # Obtenemos la información del negocio (ajusta el .first() o filtro según cómo lo guardes)
    negocio = Negocio.objects.first() 

    instagram = RedesSociales.objects.filter(plataforma__icontains='instagram').first()
    
    contexto = {
        'categorias': categorias,
        'negocio': negocio,  # <--- ¡Esto faltaba para que el footer pinte el WhatsApp, Instagram y datos del local!
        'instagram': instagram,
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

    extras_producto = producto.extras.all() if hasattr(producto, 'extras') else []

    negocio = Negocio.objects.first() 
    
    instagram = RedesSociales.objects.filter(plataforma__icontains='instagram').first()
    
    contexto = {
        'producto': producto,
        'grupos_opciones': grupos_opciones,
        'extras_producto': extras_producto,
        'negocio': negocio,  # <--- ¡Esto faltaba para que el footer pinte el WhatsApp, Instagram y datos del local!
        'instagram': instagram,
    }
    return render(request, 'detalleProducto.html', contexto)

def procesar_checkout(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        telefono = request.POST.get('telefono')
        
        calle = request.POST.get('calle')
        numero = request.POST.get('numero')
        piso = request.POST.get('piso')
        localidad = request.POST.get('localidad')
        
        id_medio_pago = request.POST.get('medio_pago')
        comentario = request.POST.get('comentario', '')

        cliente = Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono
        )

        Direccion.objects.create(
            idcliente=cliente,
            calle=calle,
            numero=numero,
            piso=piso,
            localidad=localidad
        )

        medio_pago = MedioPago.objects.get(pk=id_medio_pago)
        estado_inicial = EstadoPedido.objects.first()
        producto_ejemplo = Producto.objects.first() 

        Pedido.objects.create(
            idcliente=cliente,
            idmediopago=medio_pago,
            idestadopedido=estado_inicial,
            producto=producto_ejemplo,
            justificacioncancelacion=comentario,
            cantidad=1
        )

        return redirect('pedido_exitoso')

    medios_pago = MedioPago.objects.all()
    return render(request, 'checkout.html', {'medios_pago': medios_pago})

def pedido_exitoso(request):
    return render(request, 'pedido_exitoso.html')