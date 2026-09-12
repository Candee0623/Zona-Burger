from datetime import date, datetime
import logging
import re
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from decimal import Decimal

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
    ProductoPromocion,
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


# ==========================================
# VISTAS DE LA TIENDA PÚBLICA (CLIENTES)
# ==========================================

def index(request):
    negocio = Negocio.objects.first()
    horarios = Horario.objects.filter(idnegocio=negocio) if negocio else []
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
    total_carrito = sum(
        (Decimal(str(item.get('subtotal', 0))) for item in carrito.values()),
        Decimal('0.00'),
    )

    medios_pago_qs = MedioPago.objects.all()
    zonas_entrega_qs = ZonasEntrega.objects.all()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or (
        request.method == 'GET' and 'application/json' in request.META.get('HTTP_ACCEPT', '')
    ):
        return JsonResponse({
            'status': 'success',
            'total_carrito': str(total_carrito),
            'medios_pago': list(medios_pago_qs.values('idmediopago', 'nombremetodo')),
            'zonas_entrega': list(zonas_entrega_qs.values('idzona', 'nombre', 'costoenvio')),
        })

    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        apellido = (request.POST.get('apellido') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        calle = (request.POST.get('calle') or '').strip()
        numero = (request.POST.get('numero') or '').strip()
        piso = (request.POST.get('piso') or '').strip()
        localidad = (request.POST.get('localidad') or 'A coordinar con el vendedor').strip()
        horario_entrega = (request.POST.get('horario_entrega') or '').strip()
        id_medio_pago = request.POST.get('medio_pago')
        codigo_promo = (request.POST.get('codigo_promocion') or '').strip().upper()
        comentario = (request.POST.get('comentario') or '').strip()

        datos_previos = request.POST

        if not carrito:
            messages.error(request, 'Tu carrito está vacío.')
            return redirect('ver_carrito')

        errores = {}

        if not nombre:
            errores['nombre'] = 'Ingresá tu nombre.'
        elif len(nombre) < 2 or len(nombre) > 100:
            errores['nombre'] = 'El nombre debe tener entre 2 y 100 caracteres.'

        if not apellido:
            errores['apellido'] = 'Ingresá tu apellido.'
        elif len(apellido) < 2 or len(apellido) > 100:
            errores['apellido'] = 'El apellido debe tener entre 2 y 100 caracteres.'

        telefono_limpio = limpiar_numero_telefono(telefono)
        if not es_telefono_cliente_valido(telefono_limpio):
            errores['telefono'] = 'Ingresá un teléfono válido (solo números, entre 8 y 13 dígitos).'

        if not calle:
            errores['calle'] = 'Ingresá la calle.'
        elif len(calle) > 150:
            errores['calle'] = 'La calle es demasiado larga.'

        if not numero:
            errores['numero'] = 'Ingresá el número de la calle.'
        elif len(numero) > 20:
            errores['numero'] = 'El número de calle es demasiado largo.'

        if not id_medio_pago:
            errores['medio_pago'] = 'Seleccioná un método de pago.'

        medio_pago = MedioPago.objects.filter(pk=id_medio_pago).first() if id_medio_pago else None
        if id_medio_pago and medio_pago is None:
            errores['medio_pago'] = 'Seleccioná un método de pago válido.'

        horario_completo = None
        if horario_entrega:
            try:
                horario_completo = datetime.strptime(
                    f'{date.today()} {horario_entrega}', '%Y-%m-%d %H:%M'
                )
            except ValueError:
                errores['horario_entrega'] = 'El horario de entrega no es válido.'

        zona_obj = ZonasEntrega.objects.filter(nombre__iexact=localidad).first()
        if zona_obj and zona_obj.costoenvio is not None:
            costo_envio = Decimal(str(zona_obj.costoenvio))
            costo_envio_texto = f'${costo_envio:.2f}'
        else:
            costo_envio = Decimal('0.00')
            costo_envio_texto = 'A coordinar'

        objeto_promocion = None
        descuento_promocion = Decimal('0.00')
        mensaje_promocion = ''
        error_promocion = ''

        # VALIDACIÓN ESTRICTA: La promoción solo se procesa si el usuario ingresa una palabra clave.
        if codigo_promo:
            objeto_promocion = Promocion.objects.filter(
                palabraclave__iexact=codigo_promo
            ).first()

            if not objeto_promocion:
                error_promocion = 'El código promocional no existe.'
            elif not promocion_es_valida(objeto_promocion):
                error_promocion = 'La promoción no está vigente.'
            else:
                descuento_promocion, mensaje_promocion = calcular_descuento_promocion(
                    carrito, objeto_promocion
                )
                if descuento_promocion <= 0:
                    error_promocion = mensaje_promocion or (
                        'La promoción no aplica a los productos de tu carrito.'
                    )

            if error_promocion:
                errores['codigo_promocion'] = error_promocion
        else:
            descuento_promocion = Decimal('0.00')

        if errores:
            return render(
                request,
                'checkout.html',
                {
                    'medios_pago': list(medios_pago_qs.values('idmediopago', 'nombremetodo')),
                    'zonas_entrega': list(zonas_entrega_qs.values('idzona', 'nombre', 'costoenvio')),
                    'total_carrito': total_carrito,
                    'datos_previos': datos_previos,
                    'errores': errores,
                    'error_telefono': errores.get('telefono', ''),
                    'error_medio_pago': errores.get('medio_pago', ''),
                    'error_promocion': error_promocion,
                    'descuento_promocion': descuento_promocion,
                },
            )

        telefono = telefono_limpio
        total_general = max(
            Decimal('0.00'), total_carrito - descuento_promocion + costo_envio
        )

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
                        idpromocion=objeto_promocion.idpromocion if objeto_promocion else None,
                        horarioentregadeseado=horario_completo.time() if horario_completo else None,
                        idproducto=producto_obj.pk,
                        cantidad=item.get('cantidad', 1),
                        justificacioncancelacion=comentario,
                    )

        mensaje = '*¡Nuevo Pedido! 🍔*\n\n'
        mensaje += '*Datos del Cliente:*\n'
        mensaje += f'• Nombre: {nombre} {apellido}\n'
        mensaje += f'• Teléfono: {telefono}\n\n'

        mensaje += '*Dirección de Envío:*\n'
        mensaje += f'• Calle: {calle} {numero}'
        if piso:
            mensaje += f' (Piso/Depto: {piso})'
        mensaje += f'\n• Localidad / Zona: {localidad}\n'

        if horario_entrega:
            mensaje += f'• Horario Deseado: {horario_entrega}\n'
        if codigo_promo and objeto_promocion and descuento_promocion > 0:
            mensaje += f'• Palabra Clave Promo: {codigo_promo} (Aplicada)\n'
        mensaje += '\n'

        mensaje += '*Detalle del Pedido:*\n'
        subtotal_productos = Decimal('0.00')
        for item_id, item in carrito.items():
            subtotal = Decimal(str(item.get('subtotal', 0)))
            subtotal_productos += subtotal
            mensaje += f'• {item.get("cantidad")}x {item.get("nombre")} (${subtotal:.2f})\n'

            detalles = item.get('detalles', [])
            for det in detalles:
                mensaje += f'   - {det}\n'

        mensaje += f'\n• Subtotal Productos: ${subtotal_productos:.2f}\n'
        if descuento_promocion > 0:
            mensaje += f'• Descuento Promo: -${descuento_promocion:.2f}\n'
        mensaje += f'• Costo de Envío: {costo_envio_texto}\n'
        mensaje += f'*Total a Pagar:* ${total_general:.2f}\n'
        mensaje += f'*Método de Pago:* {medio_pago.nombremetodo}\n'

        if comentario:
            mensaje += f'*Comentarios:* {comentario}\n'

        negocio_obj = Negocio.objects.first()
        numero_whatsapp_raw = (
            str(negocio_obj.telefono)
            if negocio_obj and negocio_obj.telefono
            else ''
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

    return render(
        request,
        'checkout.html',
        {
            'medios_pago': list(medios_pago_qs.values('idmediopago', 'nombremetodo')),
            'zonas_entrega': list(zonas_entrega_qs.values('idzona', 'nombre', 'costoenvio')),
            'total_carrito': total_carrito,
        },
    )


def pedido_exitoso(request):
    negocio = Negocio.objects.first()
    whatsapp_url = request.session.get('whatsapp_url')
    return render(request, 'pedido_exitoso.html', {
        'negocio': negocio,
        'whatsapp_url': whatsapp_url
    })


# ==========================================
# GESTIÓN DE PROMOCIONES (PÚBLICA / ADMIN)
# ==========================================

def lista_promociones(request):
    promociones = Promocion.objects.all().order_by('-idpromocion')
    return render(
        request,
        'promociones/listaPromociones.html',
        {
            'promociones': promociones
        }
    )


def crear_promocion(request):
    productos = Producto.objects.all()

    if request.method == 'POST':
        palabraclave = request.POST.get('palabraclave')
        tipobeneficio = request.POST.get('tipobeneficio')
        valor = request.POST.get('descuento') or None
        fechainicio = request.POST.get('fechainicio')
        fechafin = request.POST.get('fechafin')
        producto_id = request.POST.get('producto')
        activo = 1 if request.POST.get('activo') == 'on' else 0

        if fechainicio and fechafin and fechafin < fechainicio:
            return render(
                request,
                'promociones/formPromocion.html',
                {
                    'productos': productos,
                    'titulo': 'Nueva promoción',
                    'tipos_beneficio': Promocion.TIPOS_BENEFICIO,
                    'promocion': request.POST,
                    'error': (
                        'La fecha de fin no puede ser anterior a la fecha de inicio.'
                    ),
                },
            )

        promocion = Promocion.objects.create(
            palabraclave=palabraclave,
            tipobeneficio=tipobeneficio,
            valor=valor,
            fechainicio=fechainicio,
            fechafin=fechafin,
            activo=activo,
        )

        producto_obj = get_object_or_404(Producto, pk=producto_id)
        ProductoPromocion.objects.create(idpromocion=promocion, idproducto=producto_obj)

        return redirect('lista_promociones')

    return render(
        request,
        'promociones/formPromocion.html',
        {
            'productos': productos,
            'titulo': 'Nueva promoción',
            'tipos_beneficio': Promocion.TIPOS_BENEFICIO,
            'promocion': {},
        },
    )


def editar_promocion(request, idpromocion):
    productos = Producto.objects.all()
    promocion = get_object_or_404(Promocion, pk=idpromocion)
    relacion_pp = ProductoPromocion.objects.filter(idpromocion=promocion).first()

    if request.method == 'POST':
        fechainicio = request.POST.get('fechainicio')
        fechafin = request.POST.get('fechafin')

        if fechainicio and fechafin and fechafin < fechainicio:
            return render(
                request,
                'promociones/formPromocion.html',
                {
                    'productos': productos,
                    'titulo': 'Modificar promoción',
                    'tipos_beneficio': Promocion.TIPOS_BENEFICIO,
                    'promocion': request.POST,
                    'producto_seleccionado': int(request.POST.get('producto', 0)),
                    'error': (
                        'La fecha de fin no puede ser anterior a la fecha de inicio.'
                    ),
                },
            )

        promocion.palabraclave = request.POST.get('palabraclave')
        promocion.tipobeneficio = request.POST.get('tipobeneficio')
        promocion.valor = request.POST.get('descuento') or None
        promocion.fechainicio = fechainicio
        promocion.fechafin = fechafin
        promocion.activo = 1 if request.POST.get('activo') == 'on' else 0
        promocion.save()

        producto_id = request.POST.get('producto')
        producto_obj = get_object_or_404(Producto, pk=producto_id)

        if relacion_pp:
            relacion_pp.idproducto = producto_obj
            relacion_pp.save()
        else:
            ProductoPromocion.objects.create(
                idpromocion=promocion, idproducto=producto_obj
            )

        return redirect('lista_promociones')

    return render(
        request,
        'promociones/formPromocion.html',
        {
            'productos': productos,
            'titulo': 'Modificar promoción',
            'tipos_beneficio': Promocion.TIPOS_BENEFICIO,
            'promocion': promocion,
            'producto_seleccionado': (
                relacion_pp.idproducto.pk
                if relacion_pp and relacion_pp.idproducto
                else None
            ),
        },
    )


def eliminar_promocion(request, idpromocion):
    promocion = get_object_or_404(Promocion, pk=idpromocion)

    if request.method == 'POST':
        with transaction.atomic():
            ProductoPromocion.objects.filter(idpromocion=promocion).delete()
            promocion.delete()
        return redirect('lista_promociones')

    return render(
        request,
        'promociones/confirmarEliminar.html',
        {
            'promocion': promocion
        }
    )


def promocion_es_valida(promocion):
    if not promocion or promocion.activo != 1:
        return False

    hoy = date.today()

    if promocion.fechainicio and hoy < promocion.fechainicio:
        return False

    if promocion.fechafin and hoy > promocion.fechafin:
        return False

    return True


def obtener_productos_promocion(promocion):
    relaciones = ProductoPromocion.objects.filter(idpromocion=promocion)
    return set(
        relaciones.values_list('idproducto_id', flat=True)
    )


def calcular_descuento_promocion(carrito, promocion):
    if not promocion:
        return Decimal('0.00'), ''

    if not promocion_es_valida(promocion):
        return Decimal('0.00'), 'La promoción no está vigente.'

    productos_validos = obtener_productos_promocion(promocion)

    if not productos_validos:
        return Decimal('0.00'), 'La promoción no tiene productos asociados.'

    unidades = []
    subtotal_elegible = Decimal('0.00')

    for item in carrito.values():
        producto_id = item.get('producto_id')

        if producto_id not in productos_validos:
            continue

        cantidad = int(item.get('cantidad', 0))
        precio_unitario = Decimal(str(item.get('precio_unitario', 0)))

        if cantidad <= 0:
            continue

        subtotal_elegible += (precio_unitario * cantidad)

        for _ in range(cantidad):
            unidades.append(precio_unitario)

    if not unidades:
        return Decimal('0.00'), 'La promoción no aplica a los productos del carrito.'

    tipo = promocion.tipobeneficio
    valor = promocion.valor or Decimal('0.00')
    descuento = Decimal('0.00')

    if tipo == '2x1':
        unidades.sort()
        cantidad_gratis = len(unidades) // 2
        descuento = sum(unidades[:cantidad_gratis], Decimal('0.00'))
        mensaje = 'Promoción 2 x 1 aplicada.'

    elif tipo == '3x2':
        unidades.sort()
        cantidad_gratis = len(unidades) // 3
        descuento = sum(unidades[:cantidad_gratis], Decimal('0.00'))
        mensaje = 'Promoción 3 x 2 aplicada.'

    elif tipo == 'PRODUCTO_GRATIS':
        descuento = min(unidades)
        mensaje = 'Producto gratis aplicado.'

    elif tipo == 'DESCUENTO_PORCENTAJE':
        porcentaje = max(Decimal('0.00'), min(valor, Decimal('100.00')))
        descuento = (subtotal_elegible * porcentaje / Decimal('100'))
        mensaje = f'Descuento del {porcentaje}% aplicado.'

    elif tipo == 'DESCUENTO_FIJO':
        descuento = min(valor, subtotal_elegible)
        mensaje = f'Descuento de ${descuento} aplicado.'

    else:
        return Decimal('0.00'), 'Tipo de promoción no válido.'

    descuento = max(Decimal('0.00'), min(descuento, subtotal_elegible))

    return descuento.quantize(Decimal('0.01')), mensaje


# ==========================================
# PANEL DE CONTROL PERSONALIZADO (ADMIN)
# ==========================================

@login_required(login_url='/panel/')
def dashboard_home(request):
    if request.method == 'POST' and 'logout' in request.POST:
        logout(request)
        return redirect('core:dashboard_home')

    context = {
        'total_pedidos': Pedido.objects.count(),
        'total_productos': Producto.objects.count(),
        'total_clientes': Cliente.objects.count(),
    }
    return render(request, 'dashboard/home.html', context)


@login_required(login_url='/panel/')
def panel_productos(request):
    productos = Producto.objects.all()
    return render(request, 'dashboard/productos_lista.html', {'productos': productos})


@login_required(login_url='/panel/')
def panel_crear_producto(request):
    form = ProductoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('core:panel_productos')
    return render(request, 'dashboard/producto_form.html', {'form': form})


@login_required(login_url='/panel/')
def panel_editar_producto(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if form.is_valid():
        form.save()
        return redirect('core:panel_productos')
    return render(request, 'dashboard/producto_form.html', {'form': form})