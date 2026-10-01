from datetime import date, datetime
from decimal import Decimal
import logging
import re
import urllib.parse
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, DecimalField, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .models import (
    AjusteStock, CategoriaProducto, Cliente, Compras,
    DetalleCompra, DetallePedido, Direccion, EstadoPedido,
    EstadoProducto, EstadoStock, Extras, GrupoOpcion,
    Horario, Insumo, MedioPago, Negocio, Opcion, Pedido,
    Producto, ProductoExtras, ProductoGrupoOpcion, ProductoPromocion,
    Promocion, Receta, RecetaInsumo, RedesSociales,
    TipoBeneficio, ZonasEntrega
)
from .forms import ExtraForm, ProductoForm


logger = logging.getLogger(__name__)

PATRON_WHATSAPP_AR = re.compile(r'^549\d{9,10}$')


def limpiar_numero_telefono(numero):
    return re.sub(r'\D', '', numero or '')


def es_numero_whatsapp_valido(numero_limpio):
    return bool(PATRON_WHATSAPP_AR.fullmatch(numero_limpio))


def es_telefono_cliente_valido(numero_limpio):
    return bool(re.fullmatch(r'\d{8,13}', numero_limpio))


# ==========================================
# 1. VISTAS DE LA TIENDA PÚBLICA (CLIENTES)
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
    return render(request, 'productos/menu.html', contexto)


def detalleProducto(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)
    relaciones_grupos = ProductoGrupoOpcion.objects.filter(idproducto=producto).select_related('idgrupo')
    grupos_opciones = []
    for rel in relaciones_grupos:
        grupo = rel.idgrupo
        if grupo:
            opciones = grupo.opcion_set.all()
            grupos_opciones.append({'grupo': grupo, 'opciones': opciones})

    extras_producto = []
    if hasattr(producto, 'productoextras_set'):
        extras_producto = [
            rel.idextra for rel in producto.productoextras_set.select_related('idextra').all() if rel.idextra
        ]
    elif hasattr(producto, 'productextras_set'):
        extras_producto = [
            rel.idextra for rel in producto.productextras_set.select_related('idextra').all() if rel.idextra
        ]

    insumos_removibles = []
    receta = Receta.objects.filter(idproducto=producto).first()
    if receta:
        insumos_removibles = RecetaInsumo.objects.filter(idreceta=receta, es_removible=True)

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
    return render(request, 'productos/detalleProducto.html', contexto)


# ==========================================
# 2. VISTAS DEL CARRITO DE COMPRAS
# ==========================================

def agregar_al_carrito(request, idproducto):
    if request.method == 'POST':
        producto = get_object_or_404(Producto, pk=idproducto)
        precio_unitario = float(producto.precio)

        # 1. Validar grupos con mínimo de selecciones obligatorio
        relaciones_grupos = ProductoGrupoOpcion.objects.filter(idproducto=producto).select_related('idgrupo')
        for rel in relaciones_grupos:
            grupo = rel.idgrupo
            if grupo:
                min_req = getattr(grupo, 'minselecciones', None) or getattr(grupo, 'min_selecciones', 0) or 0
                if min_req > 0:
                    opciones_enviadas = [v for v in request.POST.getlist(f'grupo_{grupo.idgrupo}') if v]
                    if len(opciones_enviadas) < min_req:
                        messages.error(request, f'Debés seleccionar al menos {min_req} opción(es) en "{grupo.nombre}".')
                        return redirect('detalleProducto', idproducto=producto.idproducto)

        detalle_opciones = []
        opciones_seleccionadas = []
        extras_seleccionados = {}
        insumos_quitados_ids = []

        # 2. Procesar opciones de grupos (soporta tanto radio como checkboxes múltiples)
        for key in list(request.POST.keys()):
            if key.startswith('grupo_'):
                valores_opc = request.POST.getlist(key)
                for id_opcion in valores_opc:
                    if id_opcion:
                        opcion_obj = Opcion.objects.filter(pk=id_opcion).first()
                        if opcion_obj:
                            precio_adicional = float(opcion_obj.precioadicional or 0)
                            precio_unitario += precio_adicional
                            detalle_opciones.append(opcion_obj.nombre)
                            opciones_seleccionadas.append(str(id_opcion))

            elif key.startswith('extra_'):
                id_extra = request.POST.get(key)
                extra_obj = Extras.objects.filter(pk=id_extra).first()
                if extra_obj:
                    cantidad_extra = int(request.POST.get(f'cantidad_extra_{id_extra}', 1) or 1)
                    precio_extra = float(extra_obj.precio or 0)
                    precio_unitario += precio_extra * cantidad_extra
                    detalle_opciones.append(f'{extra_obj.nombre} (x{cantidad_extra})')
                    extras_seleccionados[str(id_extra)] = cantidad_extra

            elif key.startswith('sin_insumo_'):
                id_insumo = request.POST.get(key)
                insumo_obj = Insumo.objects.filter(pk=id_insumo).first()
                if insumo_obj:
                    detalle_opciones.append(f'Sin {insumo_obj.nombreinsumo}')
                    insumos_quitados_ids.append(str(id_insumo))

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
                'insumos_quitados_ids': insumos_quitados_ids,
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
    return render(request, 'productos/carrito.html', contexto)


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


# ==========================================
# 3. VISTAS DE CHECKOUT Y PEDIDOS
# ==========================================

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

    def construir_carrito_items(carrito_dict):
        items = []
        for item in carrito_dict.values():
            cantidad = item.get('cantidad', 1) or 1
            subtotal_item = Decimal(str(item.get('subtotal', 0)))
            precio_unitario = subtotal_item / cantidad if cantidad else subtotal_item
            items.append({
                **item,
                'subtotal': subtotal_item,
                'precio_unitario': precio_unitario,
            })
        return items

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

        errores = {'codigo_promocion': ''}

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
            costo_envio_texto = 'Gratis' if costo_envio == 0 else f'${costo_envio:.2f}'
        else:
            costo_envio = Decimal('0.00')
            costo_envio_texto = 'A coordinar'

        objeto_promocion = None
        descuento_promocion = Decimal('0.00')
        mensaje_promocion = ''
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

        total_estimado = max(Decimal('0.00'), total_carrito - descuento_promocion)

        if errores.get('nombre') or errores.get('apellido') or errores.get('telefono') \
           or errores.get('calle') or errores.get('numero') or errores.get('medio_pago') \
           or errores.get('horario_entrega') or errores.get('codigo_promocion'):
            return render(
                request,
                'productos/checkout.html',
                {
                    'medios_pago': list(medios_pago_qs.values('idmediopago', 'nombremetodo')),
                    'zonas_entrega': list(zonas_entrega_qs.values('idzona', 'nombre', 'costoenvio')),
                    'total_carrito': total_carrito,
                    'total_estimado': total_estimado,
                    'carrito_items': construir_carrito_items(carrito),
                    'datos_previos': datos_previos,
                    'errores': errores,
                    'error_telefono': errores.get('telefono', ''),
                    'error_medio_pago': errores.get('medio_pago', ''),
                    'error_promocion': error_promocion,
                    'descuento_promocion': descuento_promocion,
                    'objeto_promocion': objeto_promocion,
                },
            )

        telefono = telefono_limpio
        total_general = max(
            Decimal('0.00'), total_carrito - descuento_promocion + costo_envio
        )

        # TRANSACCIÓN ATÓMICA SEGURA
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

            # 1. Creamos LA CABECERA DEL PEDIDO (Un solo registro global)
            pedido = Pedido.objects.create(
                idcliente=cliente,
                idmediopago=medio_pago,
                idestadopedido=estado_inicial,
                idpromocion=objeto_promocion.idpromocion if objeto_promocion else None,
                horarioentregadeseado=horario_completo.time() if horario_completo else None,
                total=total_general,  # Guardamos el precio total final
                justificacioncancelacion=comentario,
            )

            # 2. Creamos LOS DETALLES DEL PEDIDO (Uno por cada producto distinto en el carrito)
            for item_id, item in carrito.items():
                producto_obj = Producto.objects.filter(
                    pk=item.get('producto_id')
                ).first()
    
            if producto_obj:
                cantidad = item.get('cantidad', 1)
                subtotal_item = Decimal(str(item.get('subtotal', 0)))
                precio_unitario = subtotal_item / cantidad if cantidad else subtotal_item

                # Convertimos las opciones/detalles del carrito en un texto plano
                texto_opciones = ", ".join(item.get('detalles', [])) if isinstance(item.get('detalles'), list) else ""

                DetallePedido.objects.create(
                    idpedido=pedido,
                    idproducto=producto_obj,
                    cantidad=cantidad,
                    preciounitario=precio_unitario,
                    observaciones=texto_opciones, # <-- Guardamos las opciones aquí
                )

        # Construcción del mensaje para WhatsApp y redirección...
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

    # GET
    return render(
        request,
        'productos/checkout.html',
        {
            'medios_pago': list(medios_pago_qs.values('idmediopago', 'nombremetodo')),
            'zonas_entrega': list(zonas_entrega_qs.values('idzona', 'nombre', 'costoenvio')),
            'total_carrito': total_carrito,
            'total_estimado': total_carrito,
            'carrito_items': construir_carrito_items(carrito),
            'errores': {'codigo_promocion': ''},
            'codigo_promocion': '',
            'datos_previos': {
                'nombre': '',
                'apellido': '',
                'telefono': '',
                'calle': '',
                'numero': '',
                'piso': '',
                'localidad': '',
                'horario_entrega': '',
                'codigo_promocion': '',
                'comentario': '',
            },
            'error_telefono': '',
            'error_medio_pago': '',
            'error_promocion': '',
            'descuento_promocion': Decimal('0.00'),
            'objeto_promocion': None,
        },
    )


def pedido_exitoso(request):
    negocio = Negocio.objects.first()
    whatsapp_url = request.session.get('whatsapp_url')
    return render(request, 'productos/pedidoExitoso.html', {
        'negocio': negocio,
        'whatsapp_url': whatsapp_url
    })


# ==========================================
# 4. GESTIÓN DE PROMOCIONES
# ==========================================

def promociones_panel(request):
    return render(request, 'panel/promociones/inicio.html')

def lista_promociones(request):

    promociones = Promocion.objects.all()

    return render(
        request,
        'panel/promociones/listaPromociones.html',
        {
            'promociones': promociones,
        }
    )


def crear_promocion(request):
    productos = Producto.objects.all()
    tipos = TipoBeneficio.objects.all()
 
    if request.method == 'POST':
        palabraclave = request.POST.get('palabraclave')
        tipo_beneficio_id = request.POST.get('tipobeneficio')
        
        # 1. Obtenemos el tipo de beneficio seleccionado
        tipo_beneficio_obj = get_object_or_404(TipoBeneficio, pk=tipo_beneficio_id)
        
        # 2. Capturamos el valor del descuento enviado por el formulario
        valor_raw = request.POST.get('descuento')
        
        # 3. Validamos según el comportamiento del tipo de beneficio que manda tu HTML
        # Si el tipo es 'SIN_VALOR' (ej: 2x1), forzamos el valor a None (NULL en la BD)
        if tipo_beneficio_obj.comportamiento == 'SIN_VALOR' or not valor_raw:
            valor = None
        else:
            valor = valor_raw

        fechainicio = request.POST.get('fechainicio') or None
        fechafin = request.POST.get('fechafin') or None
        producto_id = request.POST.get('producto')
        activo = 1 if request.POST.get('activo') == 'on' else 0
 
        # Validación de fechas
        if fechainicio and fechafin and fechafin < fechainicio:
            return render(request, 'panel/promociones/formPromocion.html', {
                'productos': productos,
                'titulo': 'Nueva promoción',
                'tipos_beneficio': tipos,
                'promocion': request.POST,
                'producto_seleccionado': int(producto_id) if producto_id else None,
                'error': 'La fecha de fin no puede ser anterior a la fecha de inicio.',
            })
 
        # Creamos la promoción con el valor limpio
        promocion = Promocion.objects.create(
            palabraclave=palabraclave,
            tipo_beneficio=tipo_beneficio_obj,
            valor=valor,
            fechainicio=fechainicio,
            fechafin=fechafin,
            activo=activo,
        )
 
        # Asociamos el producto
        producto_obj = get_object_or_404(Producto, pk=producto_id)
        ProductoPromocion.objects.create(idpromocion=promocion, idproducto=producto_obj)
        
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
    relacion_pp = ProductoPromocion.objects.filter(idpromocion=promocion).first()
 
    if request.method == 'POST':
        fechainicio = request.POST.get('fechainicio') or None
        fechafin = request.POST.get('fechafin') or None
 
        if fechainicio and fechafin and fechafin < fechainicio:
            return render(request, 'panel/promociones/formPromocion.html', {
                'productos': productos,
                'titulo': 'Modificar promoción',
                'tipos_beneficio': tipos,
                'promocion': request.POST,
                'producto_seleccionado': int(request.POST.get('producto') or 0),
                'tipo_beneficio_seleccionado': int(request.POST.get('tipobeneficio')) if request.POST.get('tipobeneficio') else None,
                'error': 'La fecha de fin no puede ser anterior a la fecha de inicio.',
            })
 
        # DIAGNÓSTICO: Esto imprimirá en tu consola negra de Django qué valor está llegando del select
        id_tipo_recibido = request.POST.get('tipobeneficio')
        print(f"--- DEBUG: ID de tipo beneficio recibido del form: {id_tipo_recibido} ---")

        tipo_beneficio_obj = get_object_or_404(
            TipoBeneficio, pk=id_tipo_recibido
        )
        
        # Capturamos el valor del descuento enviado por el formulario
        valor_raw = request.POST.get('descuento')
        
        # Validamos según el comportamiento: si es SIN_VALOR o está vacío, forzamos a None
        if tipo_beneficio_obj.comportamiento == 'SIN_VALOR' or not valor_raw:
            valor = None
        else:
            valor = valor_raw
 
        promocion.palabraclave = request.POST.get('palabraclave')
        promocion.tipobeneficio = tipo_beneficio_obj  
        promocion.valor = valor  
        promocion.fechainicio = fechainicio
        promocion.fechafin = fechafin
        promocion.activo = 1 if request.POST.get('activo') == 'on' else 0
        promocion.save()
 
        ProductoPromocion.objects.filter(idpromocion=promocion).delete()
        producto_id = request.POST.get('producto')
        if producto_id:
            producto_obj = get_object_or_404(Producto, pk=producto_id)
            ProductoPromocion.objects.create(idpromocion=promocion, idproducto=producto_obj)
 
        return redirect('lista_promociones')
 
    return render(request, 'panel/promociones/formPromocion.html', {
        'productos': productos,
        'titulo': 'Modificar promoción',
        'tipos_beneficio': tipos,
        'promocion': promocion,
        'producto_seleccionado': (
            relacion_pp.idproducto.pk if relacion_pp and relacion_pp.idproducto else None
        ),
        'tipo_beneficio_seleccionado': (
            promocion.tipobeneficio.pk if promocion.tipobeneficio else None  
        ),
    })

def eliminar_promocion(request, idpromocion):
    promocion = get_object_or_404(Promocion, pk=idpromocion)
 
    if request.method == 'POST':
        with transaction.atomic():
            ProductoPromocion.objects.filter(idpromocion=promocion).delete()
            promocion.delete()
        return redirect('lista_promociones')
 
    return render(request, 'panel/promociones/confirmarEliminar.html', {
        'promocion': promocion,
    })

def lista_tipos_beneficio(request):

    tipos = TipoBeneficio.objects.all()

    return render(
        request,
        'panel/promociones/tiposBeneficio/listar.html',
        {
            'tipos': tipos
        }
    )
    

def crear_tipo_beneficio(request):

    if request.method == 'GET':
        return render(
            request,
            'panel/promociones/tiposBeneficio/crear.html'
        )

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

    # Si no se ingresa código, lo generamos automáticamente
    if not codigo:
        codigo = nombre.upper().replace(' ', '_')

    if TipoBeneficio.objects.filter(codigo__iexact=codigo).exists():
        messages.error(request, 'Ya existe un tipo de beneficio con ese código.')
        return redirect('crear_tipo_beneficio')

    if TipoBeneficio.objects.filter(nombre__iexact=nombre).exists():
        messages.error(request, 'Ya existe un tipo de beneficio con ese nombre.')
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

    tipo = get_object_or_404(
        TipoBeneficio,
        pk=pk
    )

    if request.method == 'POST':

        codigo = request.POST.get(
            'codigo',
            ''
        ).strip()

        nombre = request.POST.get(
            'nombre',
            ''
        ).strip()

        descripcion = request.POST.get(
            'descripcion',
            ''
        ).strip()

        if not nombre:
            messages.error(
                request,
                'El nombre no puede estar vacío.'
            )

            return redirect(
                'editar_tipo_beneficio',
                pk=pk
            )

        if not codigo:
            codigo = nombre.upper().replace(' ', '_')

        existe_codigo = TipoBeneficio.objects.filter(
            codigo__iexact=codigo
        ).exclude(
            pk=pk
        ).exists()

        if existe_codigo:
            messages.error(
                request,
                'Ya existe otro beneficio con ese código.'
            )

            return redirect(
                'editar_tipo_beneficio',
                pk=pk
            )

        existe_nombre = TipoBeneficio.objects.filter(
            nombre__iexact=nombre
        ).exclude(
            pk=pk
        ).exists()

        if existe_nombre:
            messages.error(
                request,
                'Ya existe otro beneficio con ese nombre.'
            )

            return redirect(
                'editar_tipo_beneficio',
                pk=pk
            )

        tipo.codigo = codigo
        tipo.nombre = nombre
        tipo.descripcion = descripcion

        tipo.save()

        messages.success(
            request,
            'Tipo de beneficio modificado correctamente.'
        )

        return redirect('lista_tipos_beneficio')

    return render(
        request,
        'panel/promociones/tiposBeneficio/editar.html',
        {
            'tipo': tipo
        }
    )


def eliminar_tipo_beneficio(request, pk):

    tipo = get_object_or_404(
        TipoBeneficio,
        pk=pk
    )

    # Verificar si existen promociones relacionadas
    if Promocion.objects.filter(
        tipo_beneficio=tipo
    ).exists():

        messages.error(
            request,
            'No puedes eliminar este beneficio porque tiene promociones asociadas.'
        )

        return redirect('lista_promociones')

    tipo.delete()

    messages.success(
        request,
        'Tipo de beneficio eliminado correctamente.'
    )

    return redirect('lista_promociones')

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

    tipo = promocion.tipobeneficio.codigo if promocion.tipobeneficio else None
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
# 5. PANEL DE ADMINISTRACIÓN - INICIO
# ==========================================

def panel_inicio(request):
    hoy = timezone.now().date()

    # Pedidos del día
    pedidos_hoy_base = Pedido.objects.filter(
        fecha_creacion__date=hoy
    )

    # Filtros
    filtro_estado = request.GET.get('estado')
    filtro_cliente = request.GET.get('cliente')

    # Estados a mostrar
    nombres_estados_deseados = [
        'Pendiente',
        'En Preparación',
        'En proceso',
        'Enviado',
        'Entregado',
        'Cancelado'
    ]

    estados_con_conteo = []

    for nombre in nombres_estados_deseados:
        try:
            estado = EstadoPedido.objects.get(
                descripcion__iexact=nombre
            )

            cantidad = pedidos_hoy_base.filter(
                idestadopedido=estado
            ).count()

            estados_con_conteo.append({
                'estado': estado,
                'cantidad': cantidad
            })

        except EstadoPedido.DoesNotExist:
            pass

    # Tabla principal
    pedidos_hoy = pedidos_hoy_base

    # Filtrar por estado
    if filtro_estado:
        pedidos_hoy = pedidos_hoy.filter(
            idestadopedido_id=filtro_estado
        )

    # Filtrar por cliente
    if filtro_cliente:
        pedidos_hoy = pedidos_hoy.filter(
            Q(idcliente__nombre__icontains=filtro_cliente) |
            Q(idcliente__apellido__icontains=filtro_cliente)
        )

    # Total de pedidos del día
    total_pedidos_hoy = pedidos_hoy_base.count()

    # Ingresos en efectivo
    total_efectivo = pedidos_hoy_base.filter(
        idmediopago__nombremetodo__iexact='efectivo',
        pagado=True
    ).aggregate(
        suma=Sum('total')
    )['suma'] or 0

    # Ingresos por transferencia
    total_transferencia = pedidos_hoy_base.filter(
        idmediopago__nombremetodo__icontains='transferencia',
        pagado=True
    ).aggregate(
        suma=Sum('total')
    )['suma'] or 0

    context = {
        'pedidos_hoy': pedidos_hoy,
        'estados_con_conteo': estados_con_conteo,
        'filtro_estado_actual': filtro_estado,
        'filtro_cliente_actual': filtro_cliente,
        'total_pedidos_hoy': total_pedidos_hoy,
        'total_efectivo': total_efectivo,
        'total_transferencia': total_transferencia,
    }

    return render(
        request,
        'panel/inicio.html',
        context
    )


def obtener_ticket_modal(request, idpedido):

    pedido = get_object_or_404(
        Pedido,
        idpedido=idpedido
    )

    detalles = DetallePedido.objects.filter(
        idpedido=pedido
    )

    direccion_cliente = None

    if pedido.idcliente:
        direccion_cliente = Direccion.objects.filter(
            idcliente=pedido.idcliente
        ).first()

    context = {
        'pedido': pedido,
        'detalles': detalles,
        'direccion_cliente': direccion_cliente,
    }

    return render(
        request,
        'panel/parcialTicket.html',
        context
    )


def actualizar_estado_pedido(request, idpedido):

    if request.method == 'POST':

        pedido = get_object_or_404(
            Pedido,
            idpedido=idpedido
        )

        nuevo_estado_id = request.POST.get(
            'nuevo_estado'
        )

        if nuevo_estado_id:

            nuevo_estado = get_object_or_404(
                EstadoPedido,
                pk=nuevo_estado_id
            )

            pedido.idestadopedido = nuevo_estado

            es_cancelado = (
                'cancelado'
                in nuevo_estado.descripcion.lower()
            )

            if es_cancelado:

                justificacion = request.POST.get(
                    'justificacioncancelacion',
                    ''
                )

                pedido.justificacioncancelacion = justificacion

            pedido.save()

            cliente = pedido.idcliente

            nombre_cliente = (
                cliente.nombre
                if cliente
                else 'Cliente'
            )

            telefono_cliente = (
                getattr(cliente, 'telefono', '')
                if cliente
                else ''
            )

            if es_cancelado:

                motivo = (
                    pedido.justificacioncancelacion
                    or 'Sin motivo especificado'
                )

                mensaje_texto = (
                    f'Hola {nombre_cliente}, '
                    f'te escribimos de Zona Burger para '
                    f'informarte que tu pedido '
                    f'#{pedido.idpedido} ha sido '
                    f'*CANCELADO*. Motivo: {motivo}.'
                )

            else:

                mensaje_texto = (
                    f'Hola {nombre_cliente}, '
                    f'te escribimos de Zona Burger. '
                    f'Tu pedido #{pedido.idpedido} '
                    f'ahora se encuentra en estado: '
                    f'*{nuevo_estado.descripcion}*.'
                )

            messages.success(
                request,
                f'Estado actualizado correctamente. '
                f'Mensaje preparado para {nombre_cliente}.'
            )

            if telefono_cliente:

                url_whatsapp = (
                    f'https://wa.me/{telefono_cliente}'
                    f'?text={urllib.parse.quote(mensaje_texto)}'
                )

                url_redirect = (
                    f"{reverse('panel_inicio')}"
                    f"?wa_url={urllib.parse.quote(url_whatsapp)}"
                )

                return redirect(url_redirect)

    return redirect('panel_inicio')


def toggle_pagado(request, idpedido):

    pedido = get_object_or_404(
        Pedido,
        pk=idpedido
    )

    pedido.pagado = not pedido.pagado
    pedido.save()

    hoy = timezone.localdate()

    ingresos_efectivo = Pedido.objects.filter(
        fecha_creacion__date=hoy,
        idmediopago__nombremetodo__iexact='efectivo',
        pagado=True
    ).aggregate(
        suma=Sum('total')
    )['suma'] or 0

    ingresos_transferencia = Pedido.objects.filter(
        fecha_creacion__date=hoy,
        idmediopago__nombremetodo__icontains='transferencia',
        pagado=True
    ).aggregate(
        suma=Sum('total')
    )['suma'] or 0

    if (
        request.headers.get('x-requested-with')
        == 'XMLHttpRequest'
        or 'application/json'
        in request.headers.get('Accept', '')
    ):

        return JsonResponse({
            'success': True,
            'pagado': pedido.pagado,
            'total_efectivo': float(
                ingresos_efectivo
            ),
            'total_transferencia': float(
                ingresos_transferencia
            )
        })

    return redirect('panel_inicio')


def ver_ticket(request, idpedido):

    pedido = get_object_or_404(
        Pedido,
        idpedido=idpedido
    )

    return HttpResponse(
        f'Visualizando el ticket del pedido #{idpedido}'
    )


def imprimir_ticket(request, idpedido):

    pedido = get_object_or_404(
        Pedido,
        idpedido=idpedido
    )

    return HttpResponse(
        f'Imprimiendo ticket del pedido #{idpedido}'
    )


def cambiar_estado_pedido(request, idpedido):

    pedido = get_object_or_404(
        Pedido,
        idpedido=idpedido
    )

    return redirect('panel_inicio')


# ==========================================
# 6. PANEL - MENÚ
# ==========================================

def menu_panel(request):

    return render(
        request,
        'panel/menu/inicio.html'
    )


# ==========================================
# 7. GESTIÓN DE CATEGORÍAS
# ==========================================

def categoria_lista(request):

    categorias = CategoriaProducto.objects.all()

    return render(
        request,
        'panel/menu/categorias/listaCategorias.html',
        {
            'categorias': categorias
        }
    )


def categoria_crear(request):

    errores = []

    if request.method == 'POST':

        nombre = request.POST.get(
            'nombre',
            ''
        ).strip()

        if not nombre:
            errores.append(
                'El nombre es obligatorio.'
            )

        if not errores:

            CategoriaProducto.objects.create(
                nombre=nombre
            )

            messages.success(
                request,
                'Categoría creada correctamente.'
            )

            return redirect('categoria_lista')

    return render(
        request,
        'panel/menu/categorias/crearCategoria.html',
        {
            'errores': errores
        }
    )


def categoria_editar(request, idcategoria):

    categoria = get_object_or_404(
        CategoriaProducto,
        pk=idcategoria
    )

    errores = []

    if request.method == 'POST':

        nombre = request.POST.get(
            'nombre',
            ''
        ).strip()

        if not nombre:

            errores.append(
                'El nombre es obligatorio.'
            )

        if not errores:

            categoria.nombre = nombre
            categoria.save()

            messages.success(
                request,
                'Categoría actualizada correctamente.'
            )

            return redirect('categoria_lista')

    return render(
        request,
        'panel/menu/categorias/editarCategoria.html',
        {
            'categoria': categoria,
            'errores': errores,
        }
    )


def categoria_eliminar(request, idcategoria):

    categoria = get_object_or_404(
        CategoriaProducto,
        pk=idcategoria
    )

    if request.method == 'POST':

        categoria.delete()

        messages.success(
            request,
            'Categoría eliminada.'
        )

        return redirect('categoria_lista')

    return render(
        request,
        'panel/menu/categorias/eliminarCategoria.html',
        {
            'titulo': 'categoría',
            'objeto': categoria,
            'cancel_url': 'categoria_lista',
        }
    )


# ==========================================
# 8. GESTIÓN DE OPCIONES Y GRUPOS
# ==========================================

def grupo_lista(request):

    grupos = GrupoOpcion.objects.prefetch_related(
        'opcion_set'
    ).all()

    return render(
        request,
        'panel/menu/opciones/listaOpciones.html',
        {
            'grupos': grupos
        }
    )


def grupo_crear(request):

    errores = []

    if request.method == 'POST':

        nombre = request.POST.get(
            'nombre',
            ''
        ).strip()

        minselecciones = request.POST.get(
            'minselecciones'
        ) or 0

        maxselecciones = request.POST.get(
            'maxselecciones'
        ) or 1

        opcion_nombres = request.POST.getlist(
            'opcion_nombre[]'
        )

        opcion_precios = request.POST.getlist(
            'opcion_precio[]'
        )

        if not nombre:

            errores.append(
                'El nombre del grupo es obligatorio.'
            )

        if not errores:

            grupo = GrupoOpcion.objects.create(
                nombre=nombre,
                minselecciones=minselecciones,
                maxselecciones=maxselecciones
            )

            for nom, prec in zip(
                opcion_nombres,
                opcion_precios
            ):

                if nom.strip():

                    Opcion.objects.create(
                        idgrupo=grupo,
                        nombre=nom.strip(),
                        precioadicional=prec or 0
                    )

            messages.success(
                request,
                'Grupo de opciones creado correctamente.'
            )

            return redirect('grupo_lista')

    return render(
        request,
        'panel/menu/opciones/crearGrupo.html',
        {
            'errores': errores
        }
    )


def grupo_editar(request, idgrupo):
    grupo = get_object_or_404(
        GrupoOpcion,
        pk=idgrupo
    )

    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        min_sel = request.POST.get('minselecciones') or 0
        max_sel = request.POST.get('maxselecciones') or 1

        opcion_ids = request.POST.getlist('opcion_id[]')
        opcion_nombres = request.POST.getlist('opcion_nombre[]')
        opcion_precios = request.POST.getlist('opcion_precio[]')
        opcion_eliminar = request.POST.getlist('opcion_eliminar[]')

        if not nombre:
            errores.append('El nombre del grupo es obligatorio.')
        else:
            with transaction.atomic():
                grupo.nombre = nombre
                grupo.minselecciones = int(min_sel) if str(min_sel).isdigit() else 0
                grupo.maxselecciones = int(max_sel) if str(max_sel).isdigit() else 1
                grupo.save()

                # 1. Eliminar opciones marcadas para eliminar
                if opcion_eliminar:
                    eliminar_ids = [int(i) for i in opcion_eliminar if str(i).isdigit()]
                    Opcion.objects.filter(idgrupo=grupo, idopcion__in=eliminar_ids).delete()

                # 2. Actualizar opciones existentes o crear nuevas
                for i in range(len(opcion_nombres)):
                    nom = opcion_nombres[i].strip() if i < len(opcion_nombres) else ''
                    prec_raw = opcion_precios[i].strip() if i < len(opcion_precios) else '0'
                    try:
                        prec = Decimal(prec_raw.replace(',', '.')) if prec_raw else Decimal('0.00')
                    except Exception:
                        prec = Decimal('0.00')

                    opc_id = opcion_ids[i].strip() if i < len(opcion_ids) else ''

                    if opc_id and str(opc_id).isdigit():
                        if str(opc_id) not in opcion_eliminar:
                            if nom:
                                Opcion.objects.filter(pk=opc_id, idgrupo=grupo).update(
                                    nombre=nom,
                                    precioadicional=prec
                                )
                            else:
                                Opcion.objects.filter(pk=opc_id, idgrupo=grupo).delete()
                    else:
                        if nom:
                            Opcion.objects.create(
                                idgrupo=grupo,
                                nombre=nom,
                                precioadicional=prec
                            )

            messages.success(
                request,
                'Grupo de opciones y sus opciones actualizados correctamente.'
            )
            return redirect('grupo_lista')

    return render(
        request,
        'panel/menu/opciones/editarGrupo.html',
        {
            'grupo': grupo,
            'opciones': grupo.opcion_set.all(),
            'errores': errores
        }
    )


def grupo_eliminar(request, idgrupo):

    grupo = get_object_or_404(
        GrupoOpcion,
        pk=idgrupo
    )

    if request.method == 'POST':

        grupo.delete()

        messages.success(
            request,
            'Grupo eliminado correctamente.'
        )

        return redirect('grupo_lista')

    return render(
        request,
        'panel/menu/opciones/eliminarGrupo.html',
        {
            'titulo': 'grupo de opciones',
            'objeto': grupo,
            'cancel_url': 'grupo_lista',
        }
    )


# ==========================================
# 9. GESTIÓN DE PRODUCTOS
# ==========================================

def producto_lista(request):
    productos = Producto.objects.select_related('idcategoria').prefetch_related(
        'productogrupoopcion_set__idgrupo',
        'productoextras_set__idextra'
    ).all().order_by('-idproducto')

    return render(
        request,
        'panel/menu/productos/listaProductos.html',
        {
            'productos': productos
        }
    )


def producto_crear(request):
    categorias = CategoriaProducto.objects.all()
    grupos = GrupoOpcion.objects.prefetch_related('opcion_set').all()
    extras = Extras.objects.all()
    errores = []

    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = request.POST.get('descripcion', '')
        precio_raw = (request.POST.get('precio') or '').strip()
        idcategoria = request.POST.get('idcategoria')
        imagen = request.FILES.get('imagen')
        grupos_ids = [int(g) for g in request.POST.getlist('grupos') if g.isdigit()]
        extras_ids = [int(e) for e in request.POST.getlist('extras') if e.isdigit()]

        if not nombre:
            errores.append('El nombre del producto es obligatorio.')

        precio = None
        try:
            precio = Decimal(precio_raw.replace(',', '.'))
            if precio < Decimal('0.00'):
                errores.append('El precio no puede ser negativo.')
        except Exception:
            errores.append('El precio debe ser un número válido.')

        cat_obj = (
            CategoriaProducto.objects.filter(pk=idcategoria).first()
            if idcategoria
            else None
        )

        if not errores:
            with transaction.atomic():
                negocio = Negocio.objects.first()
                estado_activo, _ = EstadoProducto.objects.get_or_create(descripcion='Activo')
                producto = Producto.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    precio=precio,
                    idcategoria=cat_obj,
                    idnegocio=negocio,
                    idestadoproducto=estado_activo,
                    imagen=imagen
                )

                # Guardar grupos de opciones asociados
                for gid in grupos_ids:
                    grupo_obj = GrupoOpcion.objects.filter(pk=gid).first()
                    if grupo_obj:
                        ProductoGrupoOpcion.objects.create(
                            idproducto=producto,
                            idgrupo=grupo_obj
                        )

                # Guardar extras asociados
                for eid in extras_ids:
                    extra_obj = Extras.objects.filter(pk=eid).first()
                    if extra_obj:
                        ProductoExtras.objects.create(
                            idproducto=producto,
                            idextra=extra_obj
                        )

            messages.success(
                request,
                f'Producto "{producto.nombre}" creado exitosamente.'
            )
            return redirect('producto_lista')

        return render(
            request,
            'panel/menu/productos/crearProducto.html',
            {
                'categorias': categorias,
                'grupos': grupos,
                'extras': extras,
                'errores': errores,
                'datos_previos': request.POST,
                'grupos_seleccionados': grupos_ids,
                'extras_seleccionados': extras_ids,
            }
        )

    return render(
        request,
        'panel/menu/productos/crearProducto.html',
        {
            'categorias': categorias,
            'grupos': grupos,
            'extras': extras,
            'errores': [],
            'datos_previos': {},
            'grupos_seleccionados': [],
            'extras_seleccionados': [],
        }
    )


def producto_editar(request, idproducto):
    producto = get_object_or_404(
        Producto,
        pk=idproducto
    )

    categorias = CategoriaProducto.objects.all()
    grupos = GrupoOpcion.objects.prefetch_related('opcion_set').all()
    extras = Extras.objects.all()
    errores = []

    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = request.POST.get('descripcion', '')
        precio_raw = (request.POST.get('precio') or '').strip()
        idcategoria = request.POST.get('idcategoria')
        grupos_ids = [int(g) for g in request.POST.getlist('grupos') if g.isdigit()]
        extras_ids = [int(e) for e in request.POST.getlist('extras') if e.isdigit()]

        if not nombre:
            errores.append('El nombre del producto es obligatorio.')

        try:
            precio = Decimal(precio_raw.replace(',', '.'))
            if precio < Decimal('0.00'):
                errores.append('El precio no puede ser negativo.')
        except Exception:
            errores.append('El precio debe ser un número válido.')

        if not errores:
            with transaction.atomic():
                producto.nombre = nombre
                producto.descripcion = descripcion
                producto.precio = precio
                producto.idcategoria = (
                    CategoriaProducto.objects.filter(pk=idcategoria).first()
                    if idcategoria
                    else None
                )

                if request.FILES.get('imagen'):
                    producto.imagen = request.FILES.get('imagen')

                producto.save()

                # Actualizar grupos de opciones relacionados
                ProductoGrupoOpcion.objects.filter(idproducto=producto).delete()
                for gid in grupos_ids:
                    grupo_obj = GrupoOpcion.objects.filter(pk=gid).first()
                    if grupo_obj:
                        ProductoGrupoOpcion.objects.create(
                            idproducto=producto,
                            idgrupo=grupo_obj
                        )

                # Actualizar extras relacionados
                ProductoExtras.objects.filter(idproducto=producto).delete()
                for eid in extras_ids:
                    extra_obj = Extras.objects.filter(pk=eid).first()
                    if extra_obj:
                        ProductoExtras.objects.create(
                            idproducto=producto,
                            idextra=extra_obj
                        )

            messages.success(
                request,
                f'Producto "{producto.nombre}" actualizado correctamente.'
            )
            return redirect('producto_lista')

        return render(
            request,
            'panel/menu/productos/editarProducto.html',
            {
                'producto': producto,
                'categorias': categorias,
                'grupos': grupos,
                'extras': extras,
                'errores': errores,
                'grupos_seleccionados': grupos_ids,
                'extras_seleccionados': extras_ids,
            }
        )

    # GET
    grupos_actuales = list(producto.productogrupoopcion_set.values_list('idgrupo_id', flat=True))
    extras_actuales = list(producto.productoextras_set.values_list('idextra_id', flat=True))

    return render(
        request,
        'panel/menu/productos/editarProducto.html',
        {
            'producto': producto,
            'categorias': categorias,
            'grupos': grupos,
            'extras': extras,
            'errores': [],
            'grupos_seleccionados': grupos_actuales,
            'extras_seleccionados': extras_actuales,
        }
    )


def producto_eliminar(request, idproducto):
    producto = get_object_or_404(
        Producto,
        pk=idproducto
    )

    if request.method == 'POST':
        with transaction.atomic():
            es_deshabilitado = (
                producto.idestadoproducto
                and producto.idestadoproducto.descripcion.lower() == 'deshabilitado'
            )
            if es_deshabilitado:
                estado_activo, _ = EstadoProducto.objects.get_or_create(descripcion='Activo')
                producto.idestadoproducto = estado_activo
                producto.save()
                messages.success(
                    request,
                    f'Producto "{producto.nombre}" habilitado correctamente.'
                )
            else:
                estado_deshabilitado, _ = EstadoProducto.objects.get_or_create(descripcion='Deshabilitado')
                producto.idestadoproducto = estado_deshabilitado
                producto.save()
                messages.success(
                    request,
                    f'Producto "{producto.nombre}" deshabilitado correctamente.'
                )

        return redirect('producto_lista')

    return render(
        request,
        'panel/menu/productos/eliminarProducto.html',
        {
            'producto': producto,
            'cancel_url': 'producto_lista',
        }
    )


# ==========================================
# 10. GESTIÓN DE EXTRAS
# ==========================================

def extra_lista(request):
    extras = Extras.objects.all().order_by('idextra')
    extras_con_conteo = []

    for extra in extras:
        cant = ProductoExtras.objects.filter(idextra=extra).count()
        extras_con_conteo.append({
            'extra': extra,
            'cant_productos': cant
        })

    return render(
        request,
        'panel/menu/extras/listaExtras.html',
        {
            'extras_con_conteo': extras_con_conteo
        }
    )


def extra_crear(request):
    errores = []

    if request.method == 'POST':
        form = ExtraForm(request.POST)
        if form.is_valid():
            extra = form.save()
            messages.success(
                request,
                f'Extra "{extra.nombre}" creado exitosamente.'
            )
            return redirect('extra_lista')
        else:
            return render(
                request,
                'panel/menu/extras/crearExtra.html',
                {
                    'form': form,
                    'errores': errores
                }
            )

    form = ExtraForm()
    return render(
        request,
        'panel/menu/extras/crearExtra.html',
        {
            'form': form,
            'errores': errores
        }
    )


def extra_editar(request, idextra):
    extra = get_object_or_404(
        Extras,
        pk=idextra
    )
    errores = []

    if request.method == 'POST':
        form = ExtraForm(request.POST, instance=extra)
        if form.is_valid():
            extra = form.save()
            messages.success(
                request,
                f'Extra "{extra.nombre}" actualizado correctamente.'
            )
            return redirect('extra_lista')
        else:
            return render(
                request,
                'panel/menu/extras/editarExtra.html',
                {
                    'extra': extra,
                    'form': form,
                    'errores': errores
                }
            )

    form = ExtraForm(instance=extra)
    return render(
        request,
        'panel/menu/extras/editarExtra.html',
        {
            'extra': extra,
            'form': form,
            'errores': errores
        }
    )


def extra_eliminar(request, idextra):
    extra = get_object_or_404(
        Extras,
        pk=idextra
    )
    cant_productos = ProductoExtras.objects.filter(idextra=extra).count()

    if request.method == 'POST':
        with transaction.atomic():
            ProductoExtras.objects.filter(idextra=extra).delete()
            nombre_extra = extra.nombre
            extra.delete()

        messages.success(
            request,
            f'Extra "{nombre_extra}" eliminado.'
        )
        return redirect('extra_lista')

    return render(
        request,
        'panel/menu/extras/eliminarExtra.html',
        {
            'extra': extra,
            'cant_productos': cant_productos,
            'cancel_url': 'extra_lista',
        }
    )


# ==========================================
# 11. GESTIÓN DE RECETAS
# ==========================================

def lista_recetas(request):

    productos = Producto.objects.all()

    return render(
        request,
        'panel/recetas/lista.html',
        {
            'productos': productos
        }
    )


def gestionar_receta(request, idproducto):
    producto = get_object_or_404(
        Producto,
        pk=idproducto
    )

    receta, creado = Receta.objects.get_or_create(
        idproducto=producto
    )

    detalles_receta = RecetaInsumo.objects.filter(
        idreceta=receta
    )

    todos_los_insumos = Insumo.objects.all()
    origen = request.GET.get('origen') or request.POST.get('origen', '')

    if request.method == 'POST':
        id_insumo = request.POST.get('id_insumo')
        cantidad = request.POST.get('cantidadinsumo')
        es_removible = (request.POST.get('es_removible') == 'on')

        if id_insumo:
            insumo_obj = get_object_or_404(
                Insumo,
                pk=id_insumo
            )

            # Cantidad opcional: si está vacía, se guarda en 0 / None
            cantidad_val = 0
            if cantidad and str(cantidad).strip():
                try:
                    cantidad_val = int(float(str(cantidad).replace(',', '.')))
                except (ValueError, TypeError):
                    cantidad_val = 0

            existe = RecetaInsumo.objects.filter(
                idreceta=receta,
                idinsumo=insumo_obj
            ).exists()

            if not existe:
                RecetaInsumo.objects.create(
                    idreceta=receta,
                    idinsumo=insumo_obj,
                    cantidadinsumo=cantidad_val,
                    es_removible=es_removible
                )
                messages.success(request, f'Insumo "{insumo_obj.nombre}" agregado a la receta.')

            url_redireccion = reverse('gestionar_receta', kwargs={'idproducto': producto.idproducto})
            if origen:
                url_redireccion += f'?origen={quote(origen)}'
            return redirect(url_redireccion)

    contexto = {
        'producto': producto,
        'receta': receta,
        'detalles_receta': detalles_receta,
        'todos_los_insumos': todos_los_insumos,
        'origen': origen,
    }

    return render(
        request,
        'panel/recetas/gestionarReceta.html',
        contexto
    )


def eliminar_insumo_receta(request, idrecetainsumo):
    detalle = get_object_or_404(
        RecetaInsumo,
        pk=idrecetainsumo
    )

    id_producto = detalle.idreceta.idproducto.idproducto
    origen = request.GET.get('origen', '')

    nombre_insumo = detalle.idinsumo.nombre if detalle.idinsumo else 'Insumo'
    detalle.delete()
    messages.success(request, f'Insumo "{nombre_insumo}" quitado de la receta.')

    url_redireccion = reverse('gestionar_receta', kwargs={'idproducto': id_producto})
    if origen:
        url_redireccion += f'?origen={quote(origen)}'
    return redirect(url_redireccion)


# ==========================================
# 11. GESTIÓN DE STOCK
# ==========================================

def stock_lista(request):

    insumos = Insumo.objects.all()

    insumos_criticos = [
        insumo
        for insumo in insumos
        if insumo.stockactual <= insumo.stockminimo
    ]

    contexto = {
        'insumos': insumos,
        'insumos_criticos': insumos_criticos
    }

    return render(
        request,
        'panel/stock/stock_lista.html',
        contexto
    )


def stock_crear(request):

    if request.method == 'POST':

        codigo = request.POST.get('codigo')
        nombreinsumo = request.POST.get('nombreinsumo')
        unidadmedidaingreso = request.POST.get(
            'unidadmedidaingreso'
        )
        unidadmedidaegreso = request.POST.get(
            'unidadmedidaegreso'
        )
        stockactual = request.POST.get(
            'stockactual',
            0
        )
        stockminimo = request.POST.get(
            'stockminimo',
            5
        )

        Insumo.objects.create(
            codigo=codigo,
            nombreinsumo=nombreinsumo,
            unidadmedidaingreso=unidadmedidaingreso,
            unidadmedidaegreso=unidadmedidaegreso,
            stockactual=stockactual,
            stockminimo=stockminimo
        )

        messages.success(
            request,
            'Insumo creado correctamente en el stock.'
        )

        return redirect('stock_lista')

    return render(
        request,
        'panel/stock/stock_form.html'
    )


def registrar_compra_insumo(request):

    insumos = Insumo.objects.all()

    if request.method == 'POST':

        idinsumo = request.POST.get(
            'idinsumo'
        )

        cantidad = float(
            request.POST.get(
                'cantidad',
                0
            )
        )

        costounitario = float(
            request.POST.get(
                'costounitario',
                0
            )
        )

        insumo = get_object_or_404(
            Insumo,
            pk=idinsumo
        )

        with transaction.atomic():

            compra = Compras.objects.create(
                fecha=datetime.now(),
                preciototal=cantidad * costounitario,
                idempleado=None
            )

            DetalleCompra.objects.create(
                idcompra=compra,
                idinsumo=insumo,
                cantidad=cantidad,
                costounitario=costounitario
            )

            insumo.stockactual += Decimal(
                str(cantidad)
            )

            insumo.save()

        messages.success(
            request,
            'Compra registrada y stock actualizado con éxito.'
        )

        return redirect('stock_lista')

    return render(
        request,
        'panel/stock/registrar_compra.html',
        {
            'insumos': insumos
        }
    )


def ajustar_stock(request, idinsumo):

    insumo = get_object_or_404(
        Insumo,
        pk=idinsumo
    )

    if request.method == 'POST':

        nueva_cantidad = request.POST.get(
            'stockactual'
        )

        motivo = request.POST.get(
            'motivo'
        )

        if motivo and motivo.strip():

            cantidad_anterior = insumo.stockactual

            with transaction.atomic():

                AjusteStock.objects.create(
                    idinsumo=insumo,
                    cantidadanterior=cantidad_anterior,
                    cantidadnueva=nueva_cantidad,
                    motivo=motivo.strip()
                )

                insumo.stockactual = Decimal(
                    str(nueva_cantidad)
                )

                insumo.save()

            messages.success(
                request,
                'Ajuste de stock guardado correctamente con su motivo.'
            )

            return redirect('stock_lista')

        messages.error(
            request,
            'El motivo del ajuste es obligatorio.'
        )

    return render(
        request,
        'panel/stock/ajustar_stock.html',
        {
            'insumo': insumo
        }
    )