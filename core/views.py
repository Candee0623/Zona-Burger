import logging
import re
from urllib.parse import quote
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from datetime import datetime, date
from .models import (
    CategoriaProducto,
    Cliente,
    Direccion,
    EstadoPedido,
    Extras,
    Horario,
    MedioPago,
    Negocio,
    Opcion,
    Pedido,
    Producto,
    ProductoGrupoOpcion,
    Promocion,
    RedesSociales,
    ZonasEntrega,
)
 
logger = logging.getLogger(__name__)
 
PATRON_WHATSAPP_AR = re.compile(r'^549\d{9,10}$')
 
 
def limpiar_numero_telefono(numero):
    return re.sub(r'\D', '', numero or '')
 
 
def es_numero_whatsapp_valido(numero_limpio):
    return bool(PATRON_WHATSAPP_AR.fullmatch(numero_limpio))
 
 
def es_telefono_cliente_valido(numero_limpio):
    return bool(re.fullmatch(r'\d{8,13}', numero_limpio))
 
 
def index(request):
    negocio = Negocio.objects.first()
    horarios = Horario.objects.filter(idnegocio=negocio) if negocio else []
    # ZonasEntrega.idnegocio es un IntegerField (no FK), hay que filtrar por el id, no por el objeto.
    zonas = ZonasEntrega.objects.filter(idnegocio=negocio.idnegocio) if negocio else []
    instagram = RedesSociales.objects.filter(
        plataforma__icontains='instagram'
    ).first()
    promociones_activas = Promocion.objects.filter(activo=1)
 
    context = {
        'negocio': negocio,
        'horarios': horarios,
        'zonas': zonas,
        'instagram': instagram,
        'promociones_activas': promociones_activas,
    }
    return render(request, 'index.html', context)
 
 
def menu(request):
    categorias = CategoriaProducto.objects.all()
    negocio = Negocio.objects.first()
    instagram = RedesSociales.objects.filter(
        plataforma__icontains='instagram'
    ).first()
 
    contexto = {
        'categorias': categorias,
        'negocio': negocio,
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
        grupos_opciones.append({'grupo': grupo, 'opciones': opciones})
 
    extras_producto = []
    if hasattr(producto, 'productoextras_set'):
        extras_producto = [
            rel.idextra for rel in producto.productoextras_set.all()
        ]
    elif hasattr(producto, 'productextras_set'):
        extras_producto = [rel.idextra for rel in producto.productextras_set.all()]
 
    edit_item_id = request.session.get('edit_item_id')
    item_editando = None
    if edit_item_id:
        carrito = request.session.get('carrito', {})
        if edit_item_id in carrito:
            item_editando = carrito[edit_item_id]
 
    negocio = Negocio.objects.first()
    instagram = RedesSociales.objects.filter(
        plataforma__icontains='instagram'
    ).first()
 
    contexto = {
        'producto': producto,
        'grupos_opciones': grupos_opciones,
        'extras_producto': extras_producto,
        'negocio': negocio,
        'instagram': instagram,
        'item_editando': item_editando,
        'edit_item_id': edit_item_id,
    }
    return render(request, 'detalleProducto.html', contexto)
 
 
def agregar_al_carrito(request, idproducto):
    if request.method == 'POST':
        producto = get_object_or_404(Producto, pk=idproducto)
        precio_unitario = float(producto.precio)
 
        detalle_opciones = []
        opciones_seleccionadas = []
        extras_seleccionados = {}
 
        for key, value in request.POST.items():
            if key.startswith('grupo_'):
                id_opcion = value
                opcion_obj = Opcion.objects.filter(pk=id_opcion).first()
                if opcion_obj:
                    precio_adicional = float(opcion_obj.precioadicional or 0)
                    precio_unitario += precio_adicional
                    detalle_opciones.append(opcion_obj.nombre)
                    opciones_seleccionadas.append(str(id_opcion))
 
            elif key.startswith('extra_'):
                id_extra = value
                extra_obj = Extras.objects.filter(pk=id_extra).first()
                if extra_obj:
                    cantidad_extra = int(request.POST.get(f'cantidad_extra_{id_extra}', 1))
                    precio_extra = float(extra_obj.precio or 0)
                    precio_unitario += precio_extra * cantidad_extra
                    detalle_opciones.append(f'{extra_obj.nombre} (x{cantidad_extra})')
                    extras_seleccionados[str(id_extra)] = cantidad_extra
 
        if 'carrito' not in request.session:
            request.session['carrito'] = {}
 
        carrito = request.session['carrito']
        edit_id = request.POST.get('edit_id')
        if edit_id and edit_id in carrito:
            del carrito[edit_id]
 
        if 'edit_item_id' in request.session:
            del request.session['edit_item_id']
 
        item_id = (
            f"{idproducto}_" + '_'.join(detalle_opciones)
            if detalle_opciones
            else str(idproducto)
        )
 
        if item_id in carrito:
            carrito[item_id]['cantidad'] += 1
            carrito[item_id]['subtotal'] = (
                carrito[item_id]['cantidad'] * precio_unitario
            )
        else:
            carrito[item_id] = {
                'producto_id': producto.idproducto,
                'nombre': producto.nombre,
                'imagen': producto.imagen.url if producto.imagen else '',
                'precio_unitario': precio_unitario,
                'cantidad': 1,
                'subtotal': precio_unitario,
                'detalles': detalle_opciones,
                'opciones_ids': opciones_seleccionadas,
                'extras_ids': extras_seleccionados,
            }
 
        request.session.modified = True
        return redirect('ver_carrito')
 
    return redirect('menu')
 
 
def editar_item_carrito(request, item_id):
    carrito = request.session.get('carrito', {})
    if item_id in carrito:
        item = carrito[item_id]
        request.session['edit_item_id'] = item_id
        return redirect('detalleProducto', idproducto=item['producto_id'])
    return redirect('ver_carrito')
 
 
def ver_carrito(request):
    if 'edit_item_id' in request.session:
        del request.session['edit_item_id']
        request.session.modified = True
 
    carrito = request.session.get('carrito', {})
    total_carrito = sum(item['subtotal'] for item in carrito.values())
 
    negocio = Negocio.objects.first()
    instagram = RedesSociales.objects.filter(
        plataforma__icontains='instagram'
    ).first()
 
    contexto = {
        'carrito': carrito,
        'total_carrito': total_carrito,
        'negocio': negocio,
        'instagram': instagram,
    }
    return render(request, 'carrito.html', contexto)
 
 
def actualizar_cantidad_carrito(request, item_id, accion):
    carrito = request.session.get('carrito', {})
    if item_id in carrito:
        if accion == 'aumentar':
            carrito[item_id]['cantidad'] += 1
        elif accion == 'disminuir':
            carrito[item_id]['cantidad'] -= 1
 
        if carrito[item_id]['cantidad'] <= 0:
            del carrito[item_id]
        else:
            precio_unitario = float(carrito[item_id]['precio_unitario'])
            cantidad = carrito[item_id]['cantidad']
            carrito[item_id]['subtotal'] = cantidad * precio_unitario
 
        request.session.modified = True
 
    return redirect('ver_carrito')
 
 
def eliminar_del_carrito(request, item_id):
    carrito = request.session.get('carrito', {})
    if item_id in carrito:
        del carrito[item_id]
        request.session.modified = True
    return redirect('ver_carrito')
 
 
def procesar_checkout(request):
    carrito = request.session.get('carrito', {})
    total_carrito = sum(item['subtotal'] for item in carrito.values())
 
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        telefono = request.POST.get('telefono')
 
        calle = request.POST.get('calle')
        numero = request.POST.get('numero')
        piso = request.POST.get('piso', '')
        localidad = request.POST.get('localidad', 'A coordinar con el vendedor')
 
        horario_entrega = request.POST.get('horario_entrega', '')
        id_medio_pago = request.POST.get('medio_pago')
        codigo_promo = request.POST.get('codigo_promocion', '').strip()
        comentario = request.POST.get('comentario', '')
 
        medios_pago = MedioPago.objects.all()
        zonas_entrega = ZonasEntrega.objects.all()
 
        telefono_limpio = limpiar_numero_telefono(telefono)
        if not es_telefono_cliente_valido(telefono_limpio):
            return render(
                request,
                'checkout.html',
                {
                    'medios_pago': medios_pago,
                    'zonas_entrega': zonas_entrega,
                    'total_carrito': total_carrito,
                    'error_telefono': 'Ingresá un teléfono válido (solo números, entre 8 y 13 dígitos).',
                    'datos_previos': request.POST,
                },
            )
        telefono = telefono_limpio
 
        # Validamos el medio de pago ANTES de crear cliente/dirección, para no dejar
        # registros huérfanos si el valor recibido no es válido.
        medio_pago = MedioPago.objects.filter(pk=id_medio_pago).first()
        if medio_pago is None:
            return render(
                request,
                'checkout.html',
                {
                    'medios_pago': medios_pago,
                    'zonas_entrega': zonas_entrega,
                    'total_carrito': total_carrito,
                    'error_medio_pago': 'Seleccioná un método de pago válido.',
                    'datos_previos': request.POST,
                },
            )
 
        # Buscar el costo de envío correspondiente a la zona detectada por el mapa
        zona_obj = ZonasEntrega.objects.filter(nombre__iexact=localidad).first()
        if zona_obj and zona_obj.costoenvio is not None:
            costo_envio = float(zona_obj.costoenvio)
            costo_envio_texto = f'${costo_envio}'
        else:
            costo_envio = 0.00
            costo_envio_texto = 'A coordinar'
 
        objeto_promocion = None
        if codigo_promo:
            objeto_promocion = Promocion.objects.filter(
                palabraclave__iexact=codigo_promo,
                activo=1
            ).first()
 
        horario_completo = None
        if horario_entrega:
            try:
                fecha_hoy = date.today()
                horario_completo = datetime.strptime(f"{fecha_hoy} {horario_entrega}", "%Y-%m-%d %H:%M")
            except ValueError:
                horario_completo = None
 
        with transaction.atomic():
            cliente = Cliente.objects.create(
                nombre=nombre, apellido=apellido, telefono=telefono
            )
 
            Direccion.objects.create(
                idcliente=cliente,
                calle=calle,
                numero=numero,
                piso=piso,
                localidad=localidad,
            )
 
            estado_inicial = get_object_or_404(EstadoPedido, pk=1)
 
            for item_id, item in carrito.items():
                producto_obj = Producto.objects.filter(
                    pk=item.get('producto_id')
                ).first()
                if producto_obj:
                    Pedido.objects.create(
                        idcliente=cliente,
                        idmediopago=medio_pago,
                        idestadopedido=estado_inicial,
                        idpromocion=objeto_promocion.pk if objeto_promocion else None,
                        horarioentregadeseado=horario_completo.time() if horario_completo else None,
                        idproducto=producto_obj.idproducto,
                        cantidad=item.get('cantidad', 1),
                        justificacioncancelacion=comentario,
                    )
 
        mensaje = f'*¡Nuevo Pedido! 🍔*\n\n'
        mensaje += f'*Datos del Cliente:*\n'
        mensaje += f'• Nombre: {nombre} {apellido}\n'
        mensaje += f'• Teléfono: {telefono}\n\n'
 
        mensaje += f'*Dirección de Envío:*\n'
        mensaje += f'• Calle: {calle} {numero}'
        if piso:
            mensaje += f' (Piso/Depto: {piso})'
        mensaje += f'\n• Localidad / Zona: {localidad}\n'
 
        if horario_entrega:
            mensaje += f'• Horario Deseado: {horario_entrega}\n'
        if codigo_promo and objeto_promocion:
            mensaje += f'• Palabra Clave Promo: {codigo_promo} (Aplicada)\n'
        mensaje += '\n'
 
        mensaje += f'*Detalle del Pedido:*\n'
        subtotal_productos = 0
        for item_id, item in carrito.items():
            subtotal = item.get('subtotal', 0)
            subtotal_productos += subtotal
            mensaje += f'• {item.get("cantidad")}x {item.get("nombre")} (${subtotal})\n'
 
            detalles = item.get('detalles', [])
            for det in detalles:
                mensaje += f'   - {det}\n'
 
        total_general = subtotal_productos + costo_envio
 
        mensaje += f'\n• Subtotal Productos: ${subtotal_productos}\n'
        mensaje += f'• Costo de Envío: {costo_envio_texto}\n'
        mensaje += f'*Total a Pagar:* ${total_general}\n'
        mensaje += f'*Método de Pago:* {medio_pago.nombremetodo}\n'
 
        if comentario:
            mensaje += f'*Comentarios:* {comentario}\n'
 
        negocio_obj = Negocio.objects.first()
        numero_whatsapp_raw = (
            str(negocio_obj.telefono) if negocio_obj and negocio_obj.telefono else ''
        )
        numero_whatsapp = limpiar_numero_telefono(numero_whatsapp_raw)
 
        if 'carrito' in request.session:
            del request.session['carrito']
            request.session.modified = True
 
        if not numero_whatsapp:
            logger.warning('El negocio no tiene un número de WhatsApp configurado.')
            return redirect('menu')
 
        mensaje_codificado = quote(mensaje)
        whatsapp_url = f'https://wa.me/{numero_whatsapp}?text={mensaje_codificado}'
 
        request.session['whatsapp_url'] = whatsapp_url
        return redirect('pedido_exitoso')
 
    medios_pago = MedioPago.objects.all()
    zonas_entrega = ZonasEntrega.objects.all()
    return render(request, 'checkout.html', {
        'medios_pago': medios_pago,
        'zonas_entrega': zonas_entrega,
        'total_carrito': total_carrito
    })
 
 
def pedido_exitoso(request):
    negocio = Negocio.objects.first()
    whatsapp_url = request.session.get('whatsapp_url')
    return render(request, 'pedido_exitoso.html', {
        'negocio': negocio,
        'whatsapp_url': whatsapp_url
    })