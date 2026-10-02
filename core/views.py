import hashlib
import logging
import re
import urllib.parse
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ExtraForm
from .models import (
    AjusteStock,
    CategoriaProducto,
    Cliente,
    Compras,
    DetalleCompra,
    DetallePedido,
    Direccion,
    EstadoPedido,
    Extras,
    GrupoOpcion,
    Horario,
    Insumo,
    MedioPago,
    Negocio,
    Opcion,
    Pedido,
    Producto,
    ProductoExtras,
    ProductoGrupoOpcion,
    ProductoPromocion,
    Promocion,
    Receta,
    RecetaInsumo,
    RedesSociales,
    TipoBeneficio,
    ZonasEntrega,
)

logger = logging.getLogger(__name__)

# IDs de la tabla EstadoProducto.
ESTADO_ACTIVO = 1
ESTADO_OCULTO = 2
ESTADO_ELIMINADO = 3

# Estados que no se muestran en el menú público.
ESTADOS_NO_VISIBLES = [ESTADO_OCULTO, ESTADO_ELIMINADO]

# Formato de WhatsApp para Argentina: 549 + código de área + número.
PATRON_WHATSAPP_AR = re.compile(r'^549\d{9,10}$')


# ============================================================
# UTILIDADES
# ============================================================

def limpiar_numero_telefono(numero):
    return re.sub(r'\D', '', numero or '')


def es_numero_whatsapp_valido(numero_limpio):
    return bool(PATRON_WHATSAPP_AR.fullmatch(numero_limpio))


def es_telefono_cliente_valido(numero_limpio):
    return bool(re.fullmatch(r'\d{8,13}', numero_limpio))


def obtener_instagram():
    return RedesSociales.objects.filter(
        plataforma__icontains='instagram'
    ).first()


def es_peticion_ajax(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def calcular_ingresos_del_dia(pedidos):
    """Devuelve (efectivo, transferencia) cobrado en los pedidos recibidos."""
    efectivo = pedidos.filter(
        idmediopago__nombremetodo__iexact='efectivo',
        pagado=True,
    ).aggregate(suma=Sum('total'))['suma'] or 0

    transferencia = pedidos.filter(
        idmediopago__nombremetodo__icontains='transferencia',
        pagado=True,
    ).aggregate(suma=Sum('total'))['suma'] or 0

    return efectivo, transferencia


# ============================================================
# 1. TIENDA PÚBLICA
# ============================================================

def index(request):
    negocio = Negocio.objects.first()

    horarios = Horario.objects.filter(idnegocio=negocio) if negocio else []
    zonas = (
        ZonasEntrega.objects.filter(idnegocio=negocio.idnegocio)
        if negocio else []
    )

    return render(request, 'publico/index.html', {
        'negocio': negocio,
        'horarios': horarios,
        'zonas': zonas,
        'instagram': obtener_instagram(),
        'promociones_activas': Promocion.objects.filter(activo=1),
    })


def menu(request):
    productos_visibles = Producto.objects.exclude(
        idestadoproducto_id__in=ESTADOS_NO_VISIBLES
    )

    categorias = CategoriaProducto.objects.prefetch_related(
        Prefetch('producto_set', queryset=productos_visibles)
    )

    return render(request, 'publico/menu.html', {
        'categorias': categorias,
        'negocio': Negocio.objects.first(),
        'instagram': obtener_instagram(),
    })


def menu_actualizaciones(request):
    """
    Permite que el menú público se actualice sin recargar la página.

    El navegador envía la versión que tiene en el header X-Menu-Version.
    Si coincide con la actual responde {"cambios": false}; si no, devuelve
    los fragmentos HTML actualizados de productos y categorías.
    """
    categorias = CategoriaProducto.objects.prefetch_related(
        Prefetch(
            'producto_set',
            queryset=(
                Producto.objects
                .select_related('idestadoproducto')
                .exclude(idestadoproducto_id__in=ESTADOS_NO_VISIBLES)
            ),
        )
    )

    # Representación del contenido visible: si algo cambia (nombre, precio,
    # imagen, estado, categoría...) cambia el hash resultante.
    datos_menu = []

    for categoria in categorias:
        productos = []

        for producto in categoria.producto_set.all():
            productos.append({
                'id': producto.idproducto,
                'nombre': producto.nombre,
                'descripcion': producto.descripcion or '',
                'precio': str(producto.precio),
                'imagen': producto.imagen.name if producto.imagen else '',
                'estado': (
                    producto.idestadoproducto.descripcion
                    if producto.idestadoproducto else ''
                ),
            })

        datos_menu.append({
            'id': categoria.pk,
            'nombre': categoria.nombre,
            'productos': productos,
        })

    # MD5 solo para detectar cambios, no se usa con fines de seguridad.
    version_actual = hashlib.md5(
        repr(datos_menu).encode('utf-8')
    ).hexdigest()

    if request.headers.get('X-Menu-Version') == version_actual:
        return JsonResponse({'cambios': False, 'version': version_actual})

    html_productos = render(
        request,
        'components/menuProductos.html',
        {'categorias': categorias},
    ).content.decode('utf-8')

    html_categorias = render(
        request,
        'components/menuCategorias.html',
        {'categorias': categorias},
    ).content.decode('utf-8')

    return JsonResponse({
        'cambios': True,
        'version': version_actual,
        'menu': html_productos,
        'categorias': html_categorias,
    })


def detalleProducto(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)

    relaciones_grupos = (
        ProductoGrupoOpcion.objects
        .filter(idproducto=producto)
        .select_related('idgrupo')
    )

    grupos_opciones = [
        {'grupo': rel.idgrupo, 'opciones': rel.idgrupo.opcion_set.all()}
        for rel in relaciones_grupos
        if rel.idgrupo
    ]

    extras_producto = [
        rel.idextra
        for rel in producto.productoextras_set.select_related('idextra')
        if rel.idextra
    ]

    # Si el cliente viene de editar un ítem del carrito, se recupera su
    # configuración para precargar el formulario.
    edit_item_id = request.session.get('edit_item_id')
    carrito = request.session.get('carrito', {})
    item_editando = carrito.get(edit_item_id) if edit_item_id else None

    return render(request, 'publico/detalleProducto.html', {
        'producto': producto,
        'grupos_opciones': grupos_opciones,
        'extras_producto': extras_producto,
        'negocio': Negocio.objects.first(),
        'instagram': obtener_instagram(),
        'item_editando': item_editando,
        'edit_item_id': edit_item_id,
    })


# ============================================================
# 2. CARRITO
# ============================================================

def agregar_al_carrito(request, idproducto):
    if request.method != 'POST':
        return redirect('menu')

    producto = get_object_or_404(Producto, pk=idproducto)

    # Cada grupo de opciones puede exigir una cantidad mínima de selecciones.
    relaciones_grupos = (
        ProductoGrupoOpcion.objects
        .filter(idproducto=producto)
        .select_related('idgrupo')
    )

    for relacion in relaciones_grupos:
        grupo = relacion.idgrupo

        if not grupo:
            continue

        min_selecciones = int(grupo.minselecciones or 0)

        if min_selecciones <= 0:
            continue

        seleccionadas = request.POST.getlist(f'grupo_{grupo.idgrupo}')

        if len(seleccionadas) < min_selecciones:
            # Se conserva el ítem en edición para volver a cargarlo.
            edit_id = request.POST.get('edit_id')

            if edit_id:
                request.session['edit_item_id'] = edit_id

            messages.error(
                request,
                f'Debés seleccionar al menos {min_selecciones} '
                f'opción(es) en "{grupo.nombre}".'
            )

            return redirect('detalleProducto', idproducto=producto.idproducto)

    # Se arma el producto personalizado y se calcula su precio final.
    precio_unitario = float(producto.precio)
    detalle_opciones = []
    opciones_seleccionadas = []
    extras_seleccionados = {}
    insumos_quitados_ids = []

    for key, value in request.POST.items():
        if key.startswith('grupo_'):
            opcion = Opcion.objects.filter(pk=value).first()

            if opcion:
                precio_unitario += float(opcion.precioadicional or 0)
                detalle_opciones.append(opcion.nombre)
                opciones_seleccionadas.append(str(value))

        elif key.startswith('extra_'):
            extra = Extras.objects.filter(pk=value).first()

            if extra:
                cantidad_extra = int(
                    request.POST.get(f'cantidad_extra_{value}', 1)
                )
                precio_unitario += float(extra.precio or 0) * cantidad_extra
                detalle_opciones.append(f'{extra.nombre} (x{cantidad_extra})')
                extras_seleccionados[str(value)] = cantidad_extra

        elif key.startswith('sin_insumo_'):
            insumo = Insumo.objects.filter(pk=value).first()

            if insumo:
                detalle_opciones.append(f'Sin {insumo.nombreinsumo}')
                insumos_quitados_ids.append(str(value))

    carrito = request.session.setdefault('carrito', {})

    # Al editar un ítem se reemplaza la versión anterior.
    edit_id = request.POST.get('edit_id')

    if edit_id and edit_id in carrito:
        del carrito[edit_id]

    request.session.pop('edit_item_id', None)

    # El ID combina producto y opciones: dos configuraciones distintas del
    # mismo producto quedan como ítems separados.
    item_id = (
        f"{idproducto}_" + '_'.join(detalle_opciones)
        if detalle_opciones else str(idproducto)
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
            'insumos_quitados_ids': insumos_quitados_ids,
        }

    # Django no detecta cambios dentro de diccionarios anidados de la sesión.
    request.session.modified = True

    return redirect('ver_carrito')


def editar_item_carrito(request, item_id):
    carrito = request.session.get('carrito', {})

    if item_id in carrito:
        request.session['edit_item_id'] = item_id
        return redirect(
            'detalleProducto',
            idproducto=carrito[item_id]['producto_id'],
        )

    return redirect('ver_carrito')


def ver_carrito(request):
    # Al volver al carrito se descarta el estado de edición.
    if request.session.pop('edit_item_id', None) is not None:
        request.session.modified = True

    carrito = request.session.get('carrito', {})
    total_carrito = sum(item['subtotal'] for item in carrito.values())

    return render(request, 'publico/carrito.html', {
        'carrito': carrito,
        'total_carrito': total_carrito,
        'negocio': Negocio.objects.first(),
        'instagram': obtener_instagram(),
    })


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
            carrito[item_id]['subtotal'] = (
                carrito[item_id]['cantidad']
                * float(carrito[item_id]['precio_unitario'])
            )

        request.session.modified = True

    return redirect('ver_carrito')


def eliminar_del_carrito(request, item_id):
    carrito = request.session.get('carrito', {})

    if item_id in carrito:
        del carrito[item_id]
        request.session.modified = True

    return redirect('ver_carrito')


# ============================================================
# 3. CHECKOUT Y PEDIDOS
# ============================================================

def _items_checkout(carrito):
    """Convierte los importes a Decimal y calcula el precio unitario real."""
    items = []

    for item in carrito.values():
        cantidad = item.get('cantidad', 1) or 1
        subtotal = Decimal(str(item.get('subtotal', 0)))

        items.append({
            **item,
            'subtotal': subtotal,
            'precio_unitario': subtotal / cantidad,
        })

    return items


def procesar_checkout(request):
    carrito = request.session.get('carrito', {})

    total_carrito = sum(
        (Decimal(str(i.get('subtotal', 0))) for i in carrito.values()),
        Decimal('0.00'),
    )

    medios_pago = list(
        MedioPago.objects.values('idmediopago', 'nombremetodo')
    )
    zonas_entrega = list(
        ZonasEntrega.objects.values('idzona', 'nombre', 'costoenvio')
    )

    # El checkout consulta estos datos por AJAX para actualizar el formulario.
    es_consulta_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or (
            request.method == 'GET'
            and 'application/json' in request.META.get('HTTP_ACCEPT', '')
        )
    )

    if es_consulta_json:
        return JsonResponse({
            'status': 'success',
            'total_carrito': str(total_carrito),
            'medios_pago': medios_pago,
            'zonas_entrega': zonas_entrega,
        })

    contexto = {
        'medios_pago': medios_pago,
        'zonas_entrega': zonas_entrega,
        'total_carrito': total_carrito,
        'carrito_items': _items_checkout(carrito),
    }

    if request.method != 'POST':
        return render(request, 'publico/checkout.html', {
            **contexto,
            'total_estimado': total_carrito,
            'errores': {'codigo_promocion': ''},
            'codigo_promocion': '',
            'datos_previos': {
                'nombre': '', 'apellido': '', 'telefono': '', 'calle': '',
                'numero': '', 'piso': '', 'localidad': '',
                'horario_entrega': '', 'codigo_promocion': '',
                'comentario': '',
            },
            'error_telefono': '',
            'error_medio_pago': '',
            'error_promocion': '',
            'descuento_promocion': Decimal('0.00'),
            'objeto_promocion': None,
        })

    # ---------------- POST ----------------
    def campo(nombre):
        return (request.POST.get(nombre) or '').strip()

    nombre = campo('nombre')
    apellido = campo('apellido')
    telefono = campo('telefono')
    calle = campo('calle')
    numero = campo('numero')
    piso = campo('piso')
    localidad = campo('localidad') or 'A coordinar con el vendedor'
    horario_entrega = campo('horario_entrega')
    codigo_promo = campo('codigo_promocion').upper()
    comentario = campo('comentario')
    id_medio_pago = request.POST.get('medio_pago')

    if not carrito:
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('ver_carrito')

    errores = {'codigo_promocion': ''}

    if not nombre:
        errores['nombre'] = 'Ingresá tu nombre.'
    elif not 2 <= len(nombre) <= 100:
        errores['nombre'] = 'El nombre debe tener entre 2 y 100 caracteres.'

    if not apellido:
        errores['apellido'] = 'Ingresá tu apellido.'
    elif not 2 <= len(apellido) <= 100:
        errores['apellido'] = 'El apellido debe tener entre 2 y 100 caracteres.'

    telefono_limpio = limpiar_numero_telefono(telefono)

    if not es_telefono_cliente_valido(telefono_limpio):
        errores['telefono'] = (
            'Ingresá un teléfono válido '
            '(solo números, entre 8 y 13 dígitos).'
        )

    if not calle:
        errores['calle'] = 'Ingresá la calle.'
    elif len(calle) > 150:
        errores['calle'] = 'La calle es demasiado larga.'

    if not numero:
        errores['numero'] = 'Ingresá el número de la calle.'
    elif len(numero) > 20:
        errores['numero'] = 'El número de calle es demasiado largo.'

    medio_pago = None

    if not id_medio_pago:
        errores['medio_pago'] = 'Seleccioná un método de pago.'
    else:
        medio_pago = MedioPago.objects.filter(pk=id_medio_pago).first()

        if medio_pago is None:
            errores['medio_pago'] = 'Seleccioná un método de pago válido.'

    horario_deseado = None

    if horario_entrega:
        try:
            horario_deseado = datetime.strptime(horario_entrega, '%H:%M').time()
        except ValueError:
            errores['horario_entrega'] = 'El horario de entrega no es válido.'

    # Costo de envío según la zona elegida.
    zona = ZonasEntrega.objects.filter(nombre__iexact=localidad).first()

    if zona and zona.costoenvio is not None:
        costo_envio = Decimal(str(zona.costoenvio))
        costo_envio_texto = (
            'Envío gratis' if costo_envio == 0 else f'${costo_envio:.2f}'
        )
    else:
        costo_envio = Decimal('0.00')
        costo_envio_texto = 'A coordinar'

    # Promoción por palabra clave.
    objeto_promocion = None
    descuento_promocion = Decimal('0.00')
    error_promocion = ''

    if codigo_promo:
        objeto_promocion = Promocion.objects.filter(
            palabraclave__iexact=codigo_promo
        ).first()

        if not objeto_promocion:
            error_promocion = 'El código promocional no existe.'
        elif not promocion_es_valida(objeto_promocion):
            error_promocion = 'La promoción no está vigente.'
        else:
            descuento_promocion, mensaje_promocion = (
                calcular_descuento_promocion(carrito, objeto_promocion)
            )

            if descuento_promocion <= 0:
                error_promocion = (
                    mensaje_promocion
                    or 'La promoción no aplica a los productos de tu carrito.'
                )

        if error_promocion:
            errores['codigo_promocion'] = error_promocion

    if any(errores.values()):
        total_estimado = max(
            Decimal('0.00'), total_carrito - descuento_promocion
        )

        return render(request, 'productos/checkout.html', {
            **contexto,
            'total_estimado': total_estimado,
            'datos_previos': request.POST,
            'errores': errores,
            'error_telefono': errores.get('telefono', ''),
            'error_medio_pago': errores.get('medio_pago', ''),
            'error_promocion': error_promocion,
            'descuento_promocion': descuento_promocion,
            'objeto_promocion': objeto_promocion,
        })

    telefono = telefono_limpio

    total_general = max(
        Decimal('0.00'),
        total_carrito - descuento_promocion + costo_envio,
    )

    # Cliente, dirección, pedido y detalles se guardan en una sola
    # transacción: si algo falla no queda nada a medias.
    with transaction.atomic():
        cliente = Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
        )

        Direccion.objects.create(
            idcliente=cliente,
            calle=calle,
            numero=numero,
            piso=piso,
            localidad=localidad,
        )

        # El estado con ID 1 es el estado inicial de todo pedido nuevo.
        estado_inicial = get_object_or_404(EstadoPedido, pk=1)

        pedido = Pedido.objects.create(
            idcliente=cliente,
            idmediopago=medio_pago,
            idestadopedido=estado_inicial,
            idpromocion=(
                objeto_promocion.idpromocion if objeto_promocion else None
            ),
            horarioentregadeseado=horario_deseado,
            total=total_general,
            justificacioncancelacion=comentario,
        )

        for item in carrito.values():
            producto = Producto.objects.filter(
                pk=item.get('producto_id')
            ).first()

            if not producto:
                continue

            cantidad = item.get('cantidad', 1) or 1
            subtotal_item = Decimal(str(item.get('subtotal', 0)))
            detalles = item.get('detalles')

            DetallePedido.objects.create(
                idpedido=pedido,
                idproducto=producto,
                cantidad=cantidad,
                preciounitario=subtotal_item / cantidad,
                observaciones=(
                    ', '.join(detalles) if isinstance(detalles, list) else ''
                ),
            )

    # Mensaje para el WhatsApp del negocio.
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

    if objeto_promocion and descuento_promocion > 0:
        mensaje += f'• Palabra Clave Promo: {codigo_promo} (Aplicada)\n'

    mensaje += '\n*Detalle del Pedido:*\n'

    for item in carrito.values():
        subtotal = Decimal(str(item.get('subtotal', 0)))
        mensaje += (
            f'• {item.get("cantidad")}x {item.get("nombre")} '
            f'(${subtotal:.2f})\n'
        )

        for detalle in item.get('detalles', []):
            mensaje += f'   - {detalle}\n'

    mensaje += f'\n• Subtotal Productos: ${total_carrito:.2f}\n'

    if descuento_promocion > 0:
        mensaje += f'• Descuento Promo: -${descuento_promocion:.2f}\n'

    mensaje += f'• Costo de Envío: {costo_envio_texto}\n'
    mensaje += f'*Total a Pagar:* ${total_general:.2f}\n'
    mensaje += f'*Método de Pago:* {medio_pago.nombremetodo}\n'

    if comentario:
        mensaje += f'*Comentarios:* {comentario}\n'

    negocio = Negocio.objects.first()
    numero_whatsapp = limpiar_numero_telefono(
        str(negocio.telefono) if negocio and negocio.telefono else ''
    )

    # El pedido ya está guardado: se vacía el carrito.
    if 'carrito' in request.session:
        del request.session['carrito']
        request.session.modified = True

    if not numero_whatsapp:
        logger.warning(
            'El negocio no tiene un número de WhatsApp configurado.'
        )
        return redirect('menu')

    request.session['whatsapp_url'] = (
        f'https://wa.me/{numero_whatsapp}?text={quote(mensaje)}'
    )

    return redirect('pedido_exitoso')


def pedido_exitoso(request):
    return render(request, 'publico/pedidoExitoso.html', {
        'negocio': Negocio.objects.first(),
        'whatsapp_url': request.session.get('whatsapp_url'),
    })


# ============================================================
# 4. PROMOCIONES (PANEL)
# ============================================================

def _valor_beneficio(tipo_beneficio, valor_raw):
    """Los beneficios sin valor numérico (ej. 2x1) se guardan como NULL."""
    if tipo_beneficio.comportamiento == 'SIN_VALOR' or not valor_raw:
        return None

    return valor_raw


def promociones_panel(request):
    return render(request, 'panel/promociones/inicioPromociones.html')


def lista_promociones(request):
    return render(request, 'panel/promociones/listaPromociones.html', {
        'promociones': Promocion.objects.all(),
    })


def crear_promocion(request):
    productos = Producto.objects.all()
    tipos = TipoBeneficio.objects.all()

    if request.method == 'POST':
        palabraclave = request.POST.get('palabraclave')
        producto_id = request.POST.get('producto')
        fechainicio = request.POST.get('fechainicio') or None
        fechafin = request.POST.get('fechafin') or None
        activo = 1 if request.POST.get('activo') == 'on' else 0

        tipo_beneficio = get_object_or_404(
            TipoBeneficio, pk=request.POST.get('tipobeneficio')
        )
        valor = _valor_beneficio(tipo_beneficio, request.POST.get('descuento'))

        if fechainicio and fechafin and fechafin < fechainicio:
            return render(request, 'panel/promociones/formPromocion.html', {
                'productos': productos,
                'titulo': 'Nueva promoción',
                'tipos_beneficio': tipos,
                'promocion': request.POST,
                'producto_seleccionado': (
                    int(producto_id) if producto_id else None
                ),
                'error': (
                    'La fecha de fin no puede ser anterior '
                    'a la fecha de inicio.'
                ),
            })

        promocion = Promocion.objects.create(
            palabraclave=palabraclave,
            tipo_beneficio=tipo_beneficio,
            valor=valor,
            fechainicio=fechainicio,
            fechafin=fechafin,
            activo=activo,
        )

        ProductoPromocion.objects.create(
            idpromocion=promocion,
            idproducto=get_object_or_404(Producto, pk=producto_id),
        )

        return redirect('lista_promociones')

    return render(request, 'panel/promociones/formPromocion.html', {
        'productos': productos,
        'titulo': 'Nueva promoción',
        'tipos_beneficio': tipos,
        'promocion': {},
    })


def editar_promocion(request, idpromocion):
    productos = Producto.objects.all()
    tipos = TipoBeneficio.objects.all()
    promocion = get_object_or_404(Promocion, pk=idpromocion)

    relacion = ProductoPromocion.objects.filter(idpromocion=promocion).first()

    if request.method == 'POST':
        fechainicio = request.POST.get('fechainicio') or None
        fechafin = request.POST.get('fechafin') or None
        tipo_id = request.POST.get('tipobeneficio')

        if fechainicio and fechafin and fechafin < fechainicio:
            return render(request, 'panel/promociones/formPromocion.html', {
                'productos': productos,
                'titulo': 'Modificar promoción',
                'tipos_beneficio': tipos,
                'promocion': request.POST,
                'producto_seleccionado': int(request.POST.get('producto') or 0),
                'tipo_beneficio_seleccionado': int(tipo_id) if tipo_id else None,
                'error': (
                    'La fecha de fin no puede ser anterior '
                    'a la fecha de inicio.'
                ),
            })

        tipo_beneficio = get_object_or_404(TipoBeneficio, pk=tipo_id)

        promocion.palabraclave = request.POST.get('palabraclave')
        promocion.tipo_beneficio = tipo_beneficio
        promocion.valor = _valor_beneficio(
            tipo_beneficio, request.POST.get('descuento')
        )
        promocion.fechainicio = fechainicio
        promocion.fechafin = fechafin
        promocion.activo = 1 if request.POST.get('activo') == 'on' else 0
        promocion.save()

        # Se reemplaza la relación actual por el producto elegido.
        ProductoPromocion.objects.filter(idpromocion=promocion).delete()

        producto_id = request.POST.get('producto')

        if producto_id:
            ProductoPromocion.objects.create(
                idpromocion=promocion,
                idproducto=get_object_or_404(Producto, pk=producto_id),
            )

        return redirect('lista_promociones')

    return render(request, 'panel/promociones/formPromocion.html', {
        'productos': productos,
        'titulo': 'Modificar promoción',
        'tipos_beneficio': tipos,
        'promocion': promocion,
        'producto_seleccionado': (
            relacion.idproducto.pk
            if relacion and relacion.idproducto else None
        ),
        'tipo_beneficio_seleccionado': (
            promocion.tipo_beneficio.pk if promocion.tipo_beneficio else None
        ),
    })


def eliminar_promocion(request, idpromocion):
    promocion = get_object_or_404(Promocion, pk=idpromocion)

    if request.method == 'POST':
        with transaction.atomic():
            ProductoPromocion.objects.filter(idpromocion=promocion).delete()
            promocion.delete()

        return redirect('lista_promociones')

    return render(request, 'panel/promociones/EliminarPromocion.html', {
        'promocion': promocion,
    })


# ============================================================
# TIPOS DE BENEFICIO
# ============================================================

def lista_tipos_beneficio(request):
    return render(request, 'panel/promociones/tiposBeneficio/listaTiposBeneficios.html', {
        'tipos': TipoBeneficio.objects.all(),
    })


def crear_tipo_beneficio(request):
    if request.method == 'GET':
        return render(request, 'panel/promociones/tiposBeneficio/crearTipoBeneficio.html')

    codigo = request.POST.get('codigo', '').strip()
    nombre = request.POST.get('nombre', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    comportamiento = request.POST.get('comportamiento', '').strip()

    if not nombre:
        messages.error(request, 'Debes ingresar un nombre para el beneficio.')
        return redirect('crear_tipo_beneficio')

    if not comportamiento:
        messages.error(request, 'Debes seleccionar un comportamiento.')
        return redirect('crear_tipo_beneficio')

    # Si no se indica código, se genera a partir del nombre.
    if not codigo:
        codigo = nombre.upper().replace(' ', '_')

    if TipoBeneficio.objects.filter(codigo__iexact=codigo).exists():
        messages.error(
            request, 'Ya existe un tipo de beneficio con ese código.'
        )
        return redirect('crear_tipo_beneficio')

    if TipoBeneficio.objects.filter(nombre__iexact=nombre).exists():
        messages.error(
            request, 'Ya existe un tipo de beneficio con ese nombre.'
        )
        return redirect('crear_tipo_beneficio')

    TipoBeneficio.objects.create(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        comportamiento=comportamiento,
    )

    messages.success(request, 'Tipo de beneficio creado correctamente.')
    return redirect('lista_tipos_beneficio')


def editar_tipo_beneficio(request, pk):
    tipo = get_object_or_404(TipoBeneficio, pk=pk)

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if not nombre:
            messages.error(request, 'El nombre no puede estar vacío.')
            return redirect('editar_tipo_beneficio', pk=pk)

        if not codigo:
            codigo = nombre.upper().replace(' ', '_')

        # Se excluye el propio registro para poder conservar sus valores.
        if TipoBeneficio.objects.filter(codigo__iexact=codigo).exclude(pk=pk).exists():
            messages.error(request, 'Ya existe otro beneficio con ese código.')
            return redirect('editar_tipo_beneficio', pk=pk)

        if TipoBeneficio.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
            messages.error(request, 'Ya existe otro beneficio con ese nombre.')
            return redirect('editar_tipo_beneficio', pk=pk)

        tipo.codigo = codigo
        tipo.nombre = nombre
        tipo.descripcion = descripcion
        tipo.save()

        messages.success(
            request, 'Tipo de beneficio modificado correctamente.'
        )
        return redirect('lista_tipos_beneficio')

    return render(request, 'panel/promociones/tiposBeneficio/editarTipoBeneficio.html', {
        'tipo': tipo,
    })


def eliminar_tipo_beneficio(request, pk):
    tipo = get_object_or_404(TipoBeneficio, pk=pk)

    # GET: mostrar la pantalla de confirmación
    if request.method == 'GET':
        return render(
            request,
            'panel/promociones/tiposBeneficio/eliminarTipoBeneficio.html',
            {
                'tipo': tipo,
            }
        )

    # POST: verificar si el tipo está siendo utilizado
    if Promocion.objects.filter(tipobeneficio=tipo).exists():
        messages.error(
            request,
            'No puedes eliminar este beneficio porque tiene promociones asociadas.'
        )
        return redirect('panel_lista_tipos_beneficio')

    # Eliminar si no está asociado a ninguna promoción
    tipo.delete()

    messages.success(
        request,
        'Tipo de beneficio eliminado correctamente.'
    )

    return redirect('panel_lista_tipos_beneficio')


# ============================================================
# VALIDACIÓN Y CÁLCULO DE PROMOCIONES
# ============================================================

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
    return set(
        ProductoPromocion.objects
        .filter(idpromocion=promocion)
        .values_list('idproducto_id', flat=True)
    )


def calcular_descuento_promocion(carrito, promocion):
    """Devuelve (descuento, mensaje) para la promoción sobre el carrito."""
    if not promocion:
        return Decimal('0.00'), ''

    if not promocion_es_valida(promocion):
        return Decimal('0.00'), 'La promoción no está vigente.'

    productos_validos = obtener_productos_promocion(promocion)

    if not productos_validos:
        return Decimal('0.00'), 'La promoción no tiene productos asociados.'

    # Una entrada por cada unidad elegible, para poder aplicar
    # promociones por cantidad (2x1, 3x2).
    unidades = []
    subtotal_elegible = Decimal('0.00')

    for item in carrito.values():
        if item.get('producto_id') not in productos_validos:
            continue

        cantidad = int(item.get('cantidad', 0))

        if cantidad <= 0:
            continue

        precio_unitario = Decimal(str(item.get('precio_unitario', 0)))
        subtotal_elegible += precio_unitario * cantidad
        unidades.extend([precio_unitario] * cantidad)

    if not unidades:
        return (
            Decimal('0.00'),
            'La promoción no aplica a los productos del carrito.',
        )

    tipo = promocion.tipo_beneficio.codigo if promocion.tipo_beneficio else None
    valor = promocion.valor or Decimal('0.00')

    if tipo == '2x1':
        # Las unidades más baratas son las que se regalan.
        unidades.sort()
        descuento = sum(unidades[:len(unidades) // 2], Decimal('0.00'))
        mensaje = 'Promoción 2 x 1 aplicada.'

    elif tipo == '3x2':
        unidades.sort()
        descuento = sum(unidades[:len(unidades) // 3], Decimal('0.00'))
        mensaje = 'Promoción 3 x 2 aplicada.'

    elif tipo == 'PRODUCTO_GRATIS':
        descuento = min(unidades)
        mensaje = 'Producto gratis aplicado.'

    elif tipo == 'DESCUENTO_PORCENTAJE':
        porcentaje = max(Decimal('0.00'), min(valor, Decimal('100.00')))
        descuento = subtotal_elegible * porcentaje / Decimal('100')
        mensaje = f'Descuento del {porcentaje}% aplicado.'

    elif tipo == 'DESCUENTO_FIJO':
        descuento = min(valor, subtotal_elegible)
        mensaje = f'Descuento de ${descuento} aplicado.'

    else:
        return Decimal('0.00'), 'Tipo de promoción no válido.'

    # El descuento nunca es negativo ni supera lo que cubre la promoción.
    descuento = max(Decimal('0.00'), min(descuento, subtotal_elegible))

    return descuento.quantize(Decimal('0.01')), mensaje


# ============================================================
# 5. PANEL - INICIO Y PEDIDOS
# ============================================================

def panel_inicio(request):
    hoy = timezone.localdate()
    pedidos_hoy_base = Pedido.objects.filter(fecha_creacion__date=hoy)

    filtro_estado = request.GET.get('estado')
    filtro_cliente = request.GET.get('cliente', '').strip()

    # Resumen: cantidad de pedidos de hoy por estado.
    nombres_estados = [
        'Pendiente',
        'En Preparación',
        'En proceso',
        'Enviado',
        'Entregado',
        'Cancelado',
    ]

    estados_con_conteo = []

    for nombre in nombres_estados:
        estado = EstadoPedido.objects.filter(descripcion__iexact=nombre).first()

        # Si el estado todavía no existe en la base, se omite del resumen.
        if estado:
            estados_con_conteo.append({
                'estado': estado,
                'cantidad': pedidos_hoy_base.filter(
                    idestadopedido=estado
                ).count(),
            })

    pedidos_hoy = pedidos_hoy_base

    if filtro_estado:
        pedidos_hoy = pedidos_hoy.filter(idestadopedido_id=filtro_estado)

    # Búsqueda por cliente: cada palabra debe coincidir con el comienzo del
    # nombre o del apellido, sin distinguir mayúsculas.
    if filtro_cliente:
        for termino in filtro_cliente.split():
            pedidos_hoy = pedidos_hoy.filter(
                Q(idcliente__nombre__istartswith=termino)
                | Q(idcliente__apellido__istartswith=termino)
            )

    total_efectivo, total_transferencia = calcular_ingresos_del_dia(
        pedidos_hoy_base
    )

    return render(request, 'panel/inicioPanel.html', {
        'pedidos_hoy': pedidos_hoy,
        'estados_con_conteo': estados_con_conteo,
        'filtro_estado_actual': filtro_estado,
        'filtro_cliente_actual': filtro_cliente,
        'total_pedidos_hoy': pedidos_hoy_base.count(),
        'total_efectivo': total_efectivo,
        'total_transferencia': total_transferencia,
    })


def obtener_ticket_modal(request, idpedido):
    pedido = get_object_or_404(Pedido, idpedido=idpedido)

    direccion_cliente = (
        Direccion.objects.filter(idcliente=pedido.idcliente).first()
        if pedido.idcliente else None
    )

    return render(request, 'panel/parcialTicket.html', {
        'pedido': pedido,
        'detalles': DetallePedido.objects.filter(idpedido=pedido),
        'direccion_cliente': direccion_cliente,
    })


def actualizar_estado_pedido(request, idpedido):
    if request.method != 'POST':
        return redirect('panel_inicio')

    pedido = get_object_or_404(Pedido, idpedido=idpedido)
    nuevo_estado_id = request.POST.get('nuevo_estado')

    if not nuevo_estado_id:
        return redirect('panel_inicio')

    nuevo_estado = get_object_or_404(EstadoPedido, pk=nuevo_estado_id)
    pedido.idestadopedido = nuevo_estado

    es_cancelado = 'cancelado' in nuevo_estado.descripcion.lower()

    if es_cancelado:
        pedido.justificacioncancelacion = request.POST.get(
            'justificacioncancelacion', ''
        )

    pedido.save()

    cliente = pedido.idcliente
    nombre_cliente = cliente.nombre if cliente else 'Cliente'
    telefono_cliente = getattr(cliente, 'telefono', '') if cliente else ''

    if es_cancelado:
        motivo = pedido.justificacioncancelacion or 'Sin motivo especificado'
        mensaje_texto = (
            f'Hola {nombre_cliente}, te escribimos de Zona Burger para '
            f'informarte que tu pedido #{pedido.idpedido} ha sido '
            f'*CANCELADO*. Motivo: {motivo}.'
        )
    else:
        mensaje_texto = (
            f'Hola {nombre_cliente}, te escribimos de Zona Burger. '
            f'Tu pedido #{pedido.idpedido} ahora se encuentra en estado: '
            f'*{nuevo_estado.descripcion}*.'
        )

    messages.success(
        request,
        f'Estado actualizado correctamente. '
        f'Mensaje preparado para {nombre_cliente}.',
    )

    # El panel abre el enlace de WhatsApp a partir del parámetro wa_url.
    if telefono_cliente:
        url_whatsapp = (
            f'https://wa.me/{telefono_cliente}'
            f'?text={urllib.parse.quote(mensaje_texto)}'
        )

        return redirect(
            f"{reverse('panel_inicio')}"
            f"?wa_url={urllib.parse.quote(url_whatsapp)}"
        )

    return redirect('panel_inicio')


def toggle_pagado(request, idpedido):
    pedido = get_object_or_404(Pedido, pk=idpedido)
    pedido.pagado = not pedido.pagado
    pedido.save()

    # Se recalculan los ingresos del día tras el cambio.
    ingresos_efectivo, ingresos_transferencia = calcular_ingresos_del_dia(
        Pedido.objects.filter(fecha_creacion__date=timezone.localdate())
    )

    if es_peticion_ajax(request):
        return JsonResponse({
            'success': True,
            'pagado': pedido.pagado,
            'total_efectivo': float(ingresos_efectivo),
            'total_transferencia': float(ingresos_transferencia),
        })

    return redirect('panel_inicio')


# Pendientes de implementar.

def ver_ticket(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return HttpResponse(f'Visualizando el ticket del pedido #{idpedido}')


def imprimir_ticket(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return HttpResponse(f'Imprimiendo ticket del pedido #{idpedido}')


def cambiar_estado_pedido(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return redirect('panel_inicio')


# ============================================================
# 6. PANEL - MENÚ
# ============================================================

def menu_panel(request):
    return render(request, 'panel/menu/inicioMenu.html')


# ============================================================
# 7. CATEGORÍAS
# ============================================================

def categoria_lista(request):
    return render(request, 'panel/menu/categorias/listaCategorias.html', {
        'categorias': CategoriaProducto.objects.all(),
    })


def categoria_crear(request):
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            errores.append('El nombre es obligatorio.')
        else:
            CategoriaProducto.objects.create(nombre=nombre)
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/crearCategoria.html', {
        'errores': errores,
    })


def categoria_editar(request, idcategoria):
    categoria = get_object_or_404(CategoriaProducto, pk=idcategoria)
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            errores.append('El nombre es obligatorio.')
        else:
            categoria.nombre = nombre
            categoria.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/editarCategoria.html', {
        'categoria': categoria,
        'errores': errores,
    })


def categoria_eliminar(request, idcategoria):
    categoria = get_object_or_404(CategoriaProducto, pk=idcategoria)

    if request.method == 'POST':
        categoria.delete()
        messages.success(request, 'Categoría eliminada.')
        return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/eliminarCategoria.html', {
        'titulo': 'categoría',
        'objeto': categoria,
        'cancel_url': 'categoria_lista',
    })


# ============================================================
# 8. GRUPOS DE OPCIONES
# ============================================================

def grupo_lista(request):
    return render(request, 'panel/menu/opciones/listaOpciones.html', {
        'grupos': GrupoOpcion.objects.prefetch_related('opcion_set').all(),
    })


def grupo_crear(request):
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        minselecciones = request.POST.get('minselecciones') or 0
        maxselecciones = request.POST.get('maxselecciones') or 1
        opcion_nombres = request.POST.getlist('opcion_nombre[]')
        opcion_precios = request.POST.getlist('opcion_precio[]')

        if not nombre:
            errores.append('El nombre del grupo es obligatorio.')
        else:
            grupo = GrupoOpcion.objects.create(
                nombre=nombre,
                minselecciones=minselecciones,
                maxselecciones=maxselecciones,
            )

            # Las opciones llegan como listas paralelas de nombre y precio.
            for nom, precio in zip(opcion_nombres, opcion_precios):
                if nom.strip():
                    Opcion.objects.create(
                        idgrupo=grupo,
                        nombre=nom.strip(),
                        precioadicional=precio or 0,
                    )

            messages.success(
                request, 'Grupo de opciones creado correctamente.'
            )
            return redirect('grupo_lista')

    return render(request, 'panel/menu/opciones/crearGrupo.html', {
        'errores': errores,
    })


def grupo_editar(request, idgrupo):
    grupo = get_object_or_404(GrupoOpcion, pk=idgrupo)
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        grupo.minselecciones = request.POST.get('minselecciones') or 0
        grupo.maxselecciones = request.POST.get('maxselecciones') or 1

        if not nombre:
            errores.append('El nombre del grupo es obligatorio.')
        else:
            grupo.nombre = nombre
            grupo.save()
            messages.success(request, 'Grupo actualizado correctamente.')
            return redirect('grupo_lista')

    return render(request, 'panel/menu/opciones/editarGrupo.html', {
        'grupo': grupo,
        'errores': errores,
    })


def grupo_eliminar(request, idgrupo):
    grupo = get_object_or_404(GrupoOpcion, pk=idgrupo)

    if request.method == 'POST':
        grupo.delete()
        messages.success(request, 'Grupo eliminado correctamente.')
        return redirect('grupo_lista')

    return render(request, 'panel/menu/opciones/eliminarGrupo.html', {
        'titulo': 'grupo de opciones',
        'objeto': grupo,
        'cancel_url': 'grupo_lista',
    })


# ============================================================
# 9. PRODUCTOS
# ============================================================

def _ids_enviados(request, campo):
    return [int(v) for v in request.POST.getlist(campo) if v.isdigit()]


def _validar_producto(nombre, precio_raw):
    """Devuelve (precio, errores) para los datos básicos del producto."""
    errores = []

    if not nombre:
        errores.append('El nombre del producto es obligatorio.')

    precio = None

    try:
        precio = Decimal(precio_raw)

        if precio < Decimal('0.00'):
            errores.append('El precio no puede ser negativo.')

    except (InvalidOperation, ValueError, TypeError):
        errores.append('El precio debe ser un número válido.')

    return precio, errores


def _guardar_relaciones_producto(producto, grupos_ids, extras_ids):
    """Reemplaza los grupos de opciones y extras del producto."""
    ProductoGrupoOpcion.objects.filter(idproducto=producto).delete()

    for grupo in GrupoOpcion.objects.filter(pk__in=grupos_ids):
        ProductoGrupoOpcion.objects.create(idproducto=producto, idgrupo=grupo)

    ProductoExtras.objects.filter(idproducto=producto).delete()

    for extra in Extras.objects.filter(pk__in=extras_ids):
        ProductoExtras.objects.create(idproducto=producto, idextra=extra)


def producto_lista(request):
    productos = (
        Producto.objects
        .select_related('idcategoria', 'idestadoproducto')
        .prefetch_related(
            'productogrupoopcion_set__idgrupo',
            'productoextras_set__idextra',
        )
        .order_by('-idproducto')
    )

    return render(request, 'panel/menu/productos/listaProductos.html', {
        'productos': productos,
        'ESTADO_ELIMINADO': ESTADO_ELIMINADO,
        'ESTADO_OCULTO': ESTADO_OCULTO,
    })


def producto_crear(request):
    categorias = CategoriaProducto.objects.all()
    grupos = GrupoOpcion.objects.prefetch_related('opcion_set').all()
    extras = Extras.objects.all()

    contexto = {
        'categorias': categorias,
        'grupos': grupos,
        'extras': extras,
        'errores': [],
        'datos_previos': {},
        'grupos_seleccionados': [],
        'extras_seleccionados': [],
    }

    if request.method != 'POST':
        return render(
            request, 'panel/menu/productos/crearProducto.html', contexto
        )

    nombre = (request.POST.get('nombre') or '').strip()
    precio_raw = (request.POST.get('precio') or '').strip()
    idcategoria = request.POST.get('idcategoria')
    grupos_ids = _ids_enviados(request, 'grupos')
    extras_ids = _ids_enviados(request, 'extras')

    precio, errores = _validar_producto(nombre, precio_raw)

    if errores:
        return render(request, 'panel/menu/productos/crearProducto.html', {
            **contexto,
            'errores': errores,
            'datos_previos': request.POST,
            'grupos_seleccionados': grupos_ids,
            'extras_seleccionados': extras_ids,
        })

    categoria = (
        CategoriaProducto.objects.filter(pk=idcategoria).first()
        if idcategoria else None
    )

    with transaction.atomic():
        producto = Producto.objects.create(
            nombre=nombre,
            descripcion=request.POST.get('descripcion', ''),
            precio=precio,
            idcategoria=categoria,
            idnegocio=Negocio.objects.first(),
            imagen=request.FILES.get('imagen'),
        )

        _guardar_relaciones_producto(producto, grupos_ids, extras_ids)

    messages.success(
        request, f'Producto "{producto.nombre}" creado exitosamente.'
    )
    return redirect('producto_lista')


def producto_editar(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)

    contexto = {
        'producto': producto,
        'categorias': CategoriaProducto.objects.all(),
        'grupos': GrupoOpcion.objects.prefetch_related('opcion_set').all(),
        'extras': Extras.objects.all(),
    }

    if request.method != 'POST':
        return render(request, 'panel/menu/productos/editarProducto.html', {
            **contexto,
            'errores': [],
            'grupos_seleccionados': list(
                ProductoGrupoOpcion.objects
                .filter(idproducto=producto)
                .values_list('idgrupo_id', flat=True)
            ),
            'extras_seleccionados': list(
                ProductoExtras.objects
                .filter(idproducto=producto)
                .values_list('idextra_id', flat=True)
            ),
        })

    nombre = (request.POST.get('nombre') or '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    precio_raw = (request.POST.get('precio') or '').strip()
    idcategoria = request.POST.get('idcategoria')
    grupos_ids = _ids_enviados(request, 'grupos')
    extras_ids = _ids_enviados(request, 'extras')

    precio, errores = _validar_producto(nombre, precio_raw)

    if errores:
        return render(request, 'panel/menu/productos/editarProducto.html', {
            **contexto,
            'errores': errores,
            'grupos_seleccionados': grupos_ids,
            'extras_seleccionados': extras_ids,
        })

    with transaction.atomic():
        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio = precio
        producto.idcategoria = (
            CategoriaProducto.objects.filter(pk=idcategoria).first()
            if idcategoria else None
        )

        # Si no se sube una imagen nueva se conserva la actual.
        if request.FILES.get('imagen'):
            producto.imagen = request.FILES['imagen']

        producto.save()
        _guardar_relaciones_producto(producto, grupos_ids, extras_ids)

    messages.success(
        request, f'Producto "{producto.nombre}" actualizado correctamente.'
    )
    return redirect('producto_lista')


def producto_eliminar(request, idproducto):
    """
    Borrado lógico: el producto cambia a estado Eliminado (o vuelve a Activo
    si ya estaba eliminado). No se borra el registro porque lo referencian
    recetas y pedidos históricos.
    """
    producto = get_object_or_404(Producto, pk=idproducto)
    esta_eliminado = producto.idestadoproducto_id == ESTADO_ELIMINADO

    if request.method == 'POST':
        nuevo_estado = ESTADO_ACTIVO if esta_eliminado else ESTADO_ELIMINADO

        # update() evita ejecutar el save() del modelo (conversión de imagen).
        Producto.objects.filter(pk=producto.pk).update(
            idestadoproducto=nuevo_estado
        )

        messages.success(
            request,
            f'Producto "{producto.nombre}" '
            f'{"restaurado" if esta_eliminado else "eliminado"}.'
        )
        return redirect('producto_lista')

    return render(request, 'panel/menu/productos/eliminarProducto.html', {
        'producto': producto,
        'esta_eliminado': esta_eliminado,
        'cancel_url': 'producto_lista',
    })


# ============================================================
# 10. EXTRAS
# ============================================================

def extra_lista(request):
    extras_con_conteo = [
        {
            'extra': extra,
            'cant_productos': ProductoExtras.objects.filter(
                idextra=extra
            ).count(),
        }
        for extra in Extras.objects.all().order_by('idextra')
    ]

    return render(request, 'panel/menu/extras/listaExtras.html', {
        'extras_con_conteo': extras_con_conteo,
    })


def extra_crear(request):
    if request.method == 'POST':
        form = ExtraForm(request.POST)

        if form.is_valid():
            extra = form.save()
            messages.success(
                request, f'Extra "{extra.nombre}" creado exitosamente.'
            )
            return redirect('extra_lista')
    else:
        form = ExtraForm()

    return render(request, 'panel/menu/extras/crearExtra.html', {
        'form': form,
        'errores': [],
    })


def extra_editar(request, idextra):
    extra = get_object_or_404(Extras, pk=idextra)

    if request.method == 'POST':
        form = ExtraForm(request.POST, instance=extra)

        if form.is_valid():
            extra = form.save()
            messages.success(
                request, f'Extra "{extra.nombre}" actualizado correctamente.'
            )
            return redirect('extra_lista')
    else:
        form = ExtraForm(instance=extra)

    return render(request, 'panel/menu/extras/editarExtra.html', {
        'extra': extra,
        'form': form,
        'errores': [],
    })


def extra_eliminar(request, idextra):
    extra = get_object_or_404(Extras, pk=idextra)
    cant_productos = ProductoExtras.objects.filter(idextra=extra).count()

    if request.method == 'POST':
        nombre_extra = extra.nombre

        # Primero se quitan las relaciones con productos.
        with transaction.atomic():
            ProductoExtras.objects.filter(idextra=extra).delete()
            extra.delete()

        messages.success(request, f'Extra "{nombre_extra}" eliminado.')
        return redirect('extra_lista')

    return render(request, 'panel/menu/extras/eliminarExtra.html', {
        'extra': extra,
        'cant_productos': cant_productos,
        'cancel_url': 'extra_lista',
    })


# ============================================================
# 11. RECETAS
# ============================================================

def lista_recetas(request):
    return render(request, 'panel/recetas/listaRecetas.html', {
        'productos': Producto.objects.all(),
    })


def gestionar_receta(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)
    receta, _ = Receta.objects.get_or_create(idproducto=producto)

    # Permite volver a la pantalla desde la que se llegó.
    origen = request.GET.get('origen') or request.POST.get('origen', '')

    if request.method == 'POST':
        id_insumo = request.POST.get('id_insumo')
        cantidad = request.POST.get('cantidadinsumo')

        if id_insumo and cantidad:
            insumo = get_object_or_404(Insumo, pk=id_insumo)

            # Un insumo no puede estar dos veces en la misma receta.
            if not RecetaInsumo.objects.filter(
                idreceta=receta, idinsumo=insumo
            ).exists():
                RecetaInsumo.objects.create(
                    idreceta=receta,
                    idinsumo=insumo,
                    cantidadinsumo=cantidad,
                    es_removible=request.POST.get('es_removible') == 'on',
                )

            return redirect('gestionar_receta', idproducto=producto.idproducto)

    return render(request, 'panel/recetas/gestionarReceta.html', {
        'producto': producto,
        'receta': receta,
        'detalles_receta': RecetaInsumo.objects.filter(idreceta=receta),
        'todos_los_insumos': Insumo.objects.all(),
        'origen': origen,
    })


def eliminar_insumo_receta(request, idrecetainsumo):
    detalle = get_object_or_404(RecetaInsumo, pk=idrecetainsumo)

    id_producto = detalle.idreceta.idproducto.idproducto
    origen = request.GET.get('origen', '')
    nombre_insumo = (
        detalle.idinsumo.nombreinsumo if detalle.idinsumo else 'Insumo'
    )

    detalle.delete()

    messages.success(
        request, f'Insumo "{nombre_insumo}" quitado de la receta.'
    )

    url = reverse('gestionar_receta', kwargs={'idproducto': id_producto})

    if origen:
        url += f'?origen={quote(origen)}'

    return redirect(url)


# ============================================================
# 12. STOCK
# ============================================================

def stock_lista(request):
    insumos = Insumo.objects.all()

    # Críticos: stock actual igual o menor al mínimo configurado.
    insumos_criticos = [
        insumo for insumo in insumos
        if insumo.stockactual <= insumo.stockminimo
    ]

    return render(request, 'panel/stock/stock_lista.html', {
        'insumos': insumos,
        'insumos_criticos': insumos_criticos,
    })


def stock_crear(request):
    if request.method == 'POST':
        Insumo.objects.create(
            codigo=request.POST.get('codigo'),
            nombreinsumo=request.POST.get('nombreinsumo'),
            unidadmedidaingreso=request.POST.get('unidadmedidaingreso'),
            unidadmedidaegreso=request.POST.get('unidadmedidaegreso'),
            stockactual=request.POST.get('stockactual', 0),
            stockminimo=request.POST.get('stockminimo', 5),
        )

        messages.success(
            request, 'Insumo creado correctamente en el stock.'
        )
        return redirect('stock_lista')

    return render(request, 'panel/stock/stock_form.html')


def registrar_compra_insumo(request):
    if request.method == 'POST':
        insumo = get_object_or_404(Insumo, pk=request.POST.get('idinsumo'))
        cantidad = float(request.POST.get('cantidad', 0))
        costounitario = float(request.POST.get('costounitario', 0))

        with transaction.atomic():
            compra = Compras.objects.create(
                fecha=datetime.now(),
                preciototal=cantidad * costounitario,
                idempleado=None,
            )

            DetalleCompra.objects.create(
                idcompra=compra,
                idinsumo=insumo,
                cantidad=cantidad,
                costounitario=costounitario,
            )

            insumo.stockactual += Decimal(str(cantidad))
            insumo.save()

        messages.success(
            request, 'Compra registrada y stock actualizado con éxito.'
        )
        return redirect('stock_lista')

    return render(request, 'panel/stock/registrar_compra.html', {
        'insumos': Insumo.objects.all(),
    })


def ajustar_stock(request, idinsumo):
    insumo = get_object_or_404(Insumo, pk=idinsumo)

    if request.method == 'POST':
        nueva_cantidad = request.POST.get('stockactual')
        motivo = request.POST.get('motivo')

        if motivo and motivo.strip():
            with transaction.atomic():
                # Se registra el ajuste antes de modificar el stock para
                # conservar el valor anterior y el motivo.
                AjusteStock.objects.create(
                    idinsumo=insumo,
                    cantidadanterior=insumo.stockactual,
                    cantidadnueva=nueva_cantidad,
                    motivo=motivo.strip(),
                )

                insumo.stockactual = Decimal(str(nueva_cantidad))
                insumo.save()

            messages.success(
                request,
                'Ajuste de stock guardado correctamente con su motivo.',
            )
            return redirect('stock_lista')

        messages.error(request, 'El motivo del ajuste es obligatorio.')

    return render(request, 'panel/stock/ajustar_stock.html', {
        'insumo': insumo,
    })