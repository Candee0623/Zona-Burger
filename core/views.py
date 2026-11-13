import hashlib
import json
import logging
import re
import secrets
import threading
import urllib.parse
import unicodedata
from django.db import DatabaseError, IntegrityError, transaction
from .auth_backend import EmpleadoAuthBackend
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import quote
from xml.sax.saxutils import escape
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import CommonPasswordValidator, NumericPasswordValidator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Prefetch,
    Q,
    Sum,
    Value,
)
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.marker import DataPoint, Marker
    from openpyxl.chart.shapes import GraphicalProperties
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.properties import PageSetupProperties

    OPENPYXL_DISPONIBLE = True
except ImportError:
    OPENPYXL_DISPONIBLE = False
try:
    from reportlab.graphics.charts.barcharts import (
        HorizontalBarChart,
        VerticalBarChart,
    )
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_DISPONIBLE = True
except ImportError:
    REPORTLAB_DISPONIBLE = False
from .forms import ExtraForm
from .models import (
    AjusteStock, CategoriaProducto, Cliente, Compras, DetalleCompra,
    DetallePedido, Direccion, Empleado, EstadoNegocio, EstadoPedido, Extras, GrupoOpcion,
    Horario, Insumo, Lote, MedioPago, MovimientoStock, Negocio, Opcion, Pedido, Permiso,
    Producto, ProductoExtras, ProductoGrupoOpcion, ProductoPromocion,
    Promocion, Receta, RecetaInsumo, RedesSociales, RegistroAuditoria, Rol, RolPermiso,
    TipoBeneficio, UltimaModificacion, ZonasEntrega,
)
from .decorators import (
    panel_login_requerido,
    registrar_permiso,
    requiere_permiso,
    requiere_algun_permiso,
)
from .utils import (
    registrar_auditoria,
    obtener_ip_cliente,
    generar_codigo_barras_svg,
    verificar_bloqueo_fuerza_bruta,
    registrar_intento_fallido_login,
    limpiar_intentos_fallidos_login,
)
from .stock_service import (
    calcular_consumo_carrito,
    descontar_stock_pedido,
    reintegrar_stock_pedido,
    verificar_stock_disponible,
    StockInsuficienteError,
    registrar_ingreso_lote,
    ajustar_stock_insumo,
    StockCambiadoError,
    dar_baja_lote,
    TIPO_CARGA_INICIAL,
)
from .unidades import UNIDADES_SUGERIDAS, normalizar_unidad, unidades_compatibles

logger = logging.getLogger(__name__)

# IDs de la tabla EstadoProducto.
ESTADO_ACTIVO = 1
ESTADO_OCULTO = 2
ESTADO_ELIMINADO = 3

# Estados que no se muestran en el menú público.
ESTADOS_NO_VISIBLES = [ESTADO_OCULTO, ESTADO_ELIMINADO]

# Formato de WhatsApp para Argentina: 549 + código de área + número.
PATRON_WHATSAPP_AR = re.compile(r'^549\d{9,10}$')


# UTILIDADES

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
    """Devuelve (efectivo, transferencia) cobrado, sin pedidos cancelados."""
    validos = pedidos.filter(pagado=True).exclude(
        idestadopedido__descripcion__iexact='Cancelado'
    )

    efectivo = validos.filter(
        idmediopago__nombremetodo__iexact='efectivo'
    ).aggregate(suma=Sum('total'))['suma'] or 0

    transferencia = validos.filter(
        idmediopago__nombremetodo__icontains='transferencia'
    ).aggregate(suma=Sum('total'))['suma'] or 0

    return efectivo, transferencia


# 1. TIENDA PÚBLICA

def index(request):
    negocio = Negocio.objects.first()
    hoy = timezone.localdate()

    horarios = (
        Horario.objects.filter(idnegocio=negocio)
        if negocio else Horario.objects.none()
    )

    zonas = (
        ZonasEntrega.objects.filter(
            idnegocio=negocio.idnegocio
        )
        if negocio else ZonasEntrega.objects.none()
    )

    promociones_activas = Promocion.objects.filter(
        activo=1,
    ).filter(
        Q(fechainicio__isnull=True) | Q(fechainicio__lte=hoy)
    ).filter(
        Q(fechafin__isnull=True) | Q(fechafin__gte=hoy)
    )

    return render(request, 'publico/index.html', {
        'negocio': negocio,
        'horarios': horarios,
        'zonas': zonas,
        'instagram': obtener_instagram(),
        'promociones_activas': promociones_activas,
        'estado_local': local_estado(),
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
        'estado_local': local_estado(),
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

    # Si algo visible cambia (nombre, precio, imagen, estado, categoría...)
    # cambia el hash resultante.
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


def _id_texto(valor):
    """Normaliza identificadores para compararlos con datos de sesión."""
    return str(valor)


def _decimal_seguro(valor):
    """Convierte un importe a Decimal sin aceptar valores inválidos."""
    try:
        numero = Decimal(str(valor if valor is not None else 0))
        if not numero.is_finite():
            return Decimal("0")
        return numero
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _precio_dos_decimales(valor):
    return _decimal_seguro(valor).quantize(Decimal("0.01"))


def _volver_a_detalle(request, producto, mensaje):
    """Conserva la edición cuando hay un error de validación."""
    messages.error(request, mensaje)
    return redirect("detalleProducto", idproducto=producto.idproducto)


def detalleProducto(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)

    if not _producto_disponible(producto):
        messages.error(
            request,
            "El producto seleccionado no está disponible."
        )
        return redirect("menu")

    relaciones_grupos = (
        ProductoGrupoOpcion.objects
        .filter(idproducto=producto)
        .select_related("idgrupo")
    )

    grupos_opciones = []

    for relacion in relaciones_grupos:
        grupo = relacion.idgrupo

        if not grupo:
            continue

        opciones = list(grupo.opcion_set.all())

        grupos_opciones.append({
            "grupo": grupo,
            "opciones": opciones,
        })

    relaciones_extras = producto.productoextras_set.select_related(
        "idextra"
    )

    edit_item_id = request.session.get("edit_item_id")
    carrito = request.session.get("carrito", {})

    item_editando = (
        carrito.get(str(edit_item_id))
        if edit_item_id is not None
        else None
    )

    # Compatibilidad con carritos antiguos que guardaban cantidades
    # de extras dentro de extras_ids como {id_extra: cantidad}.
    extras_seleccionados = {}

    if item_editando:
        extras_anteriores = item_editando.get("extras_ids", {})

        if isinstance(extras_anteriores, dict):
            extras_seleccionados = {
                str(k): int(v)
                for k, v in extras_anteriores.items()
            }
        elif isinstance(extras_anteriores, list):
            extras_seleccionados = {
                str(k): 1 for k in extras_anteriores
            }

    extras_producto = []

    for relacion in relaciones_extras:
        extra = relacion.idextra

        if not extra:
            continue

        extras_producto.append({
            "extra": extra,
            "seleccionado": str(extra.idextra) in extras_seleccionados,
            "cantidad": extras_seleccionados.get(
                str(extra.idextra), 1
            ),
        })

    relaciones_insumos = (
        RecetaInsumo.objects
        .filter(
            idreceta__idproducto=producto,
            es_removible=True,
            idinsumo__isnull=False,
        )
        .select_related("idinsumo")
    )

    insumos_removibles = list(relaciones_insumos)

    if item_editando:
        opciones_ids = [
            str(valor)
            for valor in item_editando.get("opciones_ids", [])
        ]

        insumos_quitados_ids = [
            str(valor)
            for valor in item_editando.get(
                "insumos_quitados_ids", []
            )
        ]
    else:
        opciones_ids = []
        insumos_quitados_ids = []

    return render(request, "publico/detalleProducto.html", {
        "producto": producto,
        "grupos_opciones": grupos_opciones,
        "extras_producto": extras_producto,
        "insumos_removibles": insumos_removibles,
        "negocio": Negocio.objects.first(),
        "instagram": obtener_instagram(),
        "item_editando": item_editando,
        "edit_item_id": edit_item_id,
        "opciones_ids_editando": opciones_ids,
        "insumos_quitados_ids_editando": insumos_quitados_ids,
        "extras_seleccionados": extras_seleccionados,
        "estado_local": local_estado(),
    })


# 2. CARRITO

def agregar_al_carrito(request, idproducto):
    if request.method != "POST":
        return redirect("menu")

    producto = get_object_or_404(Producto, pk=idproducto)

    estado = local_estado()

    if not estado.get("abierto", True):
        mensaje = (
            "En este momento el negocio está cerrado. "
            "No es posible agregar productos al carrito."
        )

        if es_peticion_ajax(request):
            return JsonResponse({
                "status": "error",
                "message": mensaje,
            }, status=400)

        messages.error(request, mensaje)

        referer = request.META.get("HTTP_REFERER")

        if referer and url_has_allowed_host_and_scheme(
            referer,
            allowed_hosts={request.get_host()},
        ):
            return redirect(referer)

        return redirect("menu")

    if not _producto_disponible(producto):
        mensaje = "El producto seleccionado no está disponible."

        if es_peticion_ajax(request):
            return JsonResponse({
                "status": "error",
                "message": mensaje,
            }, status=400)

        messages.error(request, mensaje)
        return redirect("menu")

    carrito = request.session.get("carrito", {})

    edit_id = request.POST.get("edit_id") or request.session.get(
        "edit_item_id"
    )
    edit_id = str(edit_id) if edit_id else None

    # No permitir editar un ítem que ya no está en el carrito.
    if edit_id and edit_id not in carrito:
        request.session.pop("edit_item_id", None)
        messages.error(
            request,
            "No se encontró el producto que intentabas editar. "
            "Volvé a abrirlo desde el carrito."
        )
        return redirect("ver_carrito")

    if edit_id:
        item_anterior = carrito[edit_id]

        if str(item_anterior.get("producto_id")) != str(
            producto.idproducto
        ):
            messages.error(
                request,
                "El producto que intentás editar no coincide."
            )
            return redirect("ver_carrito")

    # 1. Cargar los grupos y sus opciones válidas

    relaciones_grupos = list(
        ProductoGrupoOpcion.objects
        .filter(idproducto=producto)
        .select_related("idgrupo")
    )

    opciones_por_grupo = {}
    grupos_por_id = {}

    for relacion in relaciones_grupos:
        grupo = relacion.idgrupo

        if not grupo:
            continue

        grupo_id = str(grupo.idgrupo)
        grupos_por_id[grupo_id] = grupo

        opciones_por_grupo[grupo_id] = {
            str(opcion.pk): opcion
            for opcion in grupo.opcion_set.all()
        }

    opciones_seleccionadas = []
    detalle_opciones = []

    precio_unitario = _decimal_seguro(producto.precio)

    # 2. Validar opciones y guardar sus nombres

    for grupo_id, grupo in grupos_por_id.items():
        clave = f"grupo_{grupo_id}"
        seleccionadas = request.POST.getlist(clave)

        # No aceptar opciones repetidas.
        if len(seleccionadas) != len(set(seleccionadas)):
            return _volver_a_detalle(
                request,
                producto,
                f'Hay opciones repetidas en el grupo "{grupo.nombre}".'
            )

        minimo = max(0, int(grupo.minselecciones or 0))
        maximo = max(0, int(grupo.maxselecciones or 0))
        cantidad = len(seleccionadas)

        if cantidad < minimo:
            return _volver_a_detalle(
                request,
                producto,
                f'Debés seleccionar al menos {minimo} '
                f'opción(es) en "{grupo.nombre}".'
            )

        if maximo > 0 and cantidad > maximo:
            return _volver_a_detalle(
                request,
                producto,
                f'El grupo "{grupo.nombre}" permite un máximo '
                f'de {maximo} opción(es).'
            )

        opciones_validas = opciones_por_grupo[grupo_id]

        for opcion_id in seleccionadas:
            opcion = opciones_validas.get(str(opcion_id))

            if not opcion:
                return _volver_a_detalle(
                    request,
                    producto,
                    f'Una opción seleccionada no pertenece '
                    f'al grupo "{grupo.nombre}".'
                )

            opciones_seleccionadas.append(str(opcion.pk))

            detalle_opciones.append(
                f"{grupo.nombre}: {opcion.nombre}"
            )

            precio_unitario += _decimal_seguro(
                opcion.precioadicional
            )

    # 3. Validar extras, cantidades y precios

    relaciones_extras = (
        producto.productoextras_set
        .select_related("idextra")
    )

    extras_validos = {
        str(relacion.idextra.pk): relacion.idextra
        for relacion in relaciones_extras
        if relacion.idextra
    }

    extras_seleccionados = {}

    for clave, valor in request.POST.items():
        if not clave.startswith("extra_"):
            continue

        extra_id = clave[len("extra_"):]

        if extra_id not in extras_validos:
            return _volver_a_detalle(
                request,
                producto,
                "Se recibió un extra que no pertenece a este producto."
            )

        if str(valor) != extra_id:
            return _volver_a_detalle(
                request,
                producto,
                "La selección de un extra no es válida."
            )

        extra = extras_validos[extra_id]

        try:
            cantidad_extra = int(
                request.POST.get(
                    f"cantidad_extra_{extra_id}", "1"
                )
            )
        except (TypeError, ValueError):
            cantidad_extra = 0

        if not 1 <= cantidad_extra <= 5:
            return _volver_a_detalle(
                request,
                producto,
                f'La cantidad del extra "{extra.nombre}" '
                f'debe estar entre 1 y 5.'
            )

        extras_seleccionados[extra_id] = cantidad_extra

        precio_unitario += (
            _decimal_seguro(extra.precio) * cantidad_extra
        )

        detalle_opciones.append(
            f"Extra: {extra.nombre} (x{cantidad_extra})"
        )

    # 4. Validar ingredientes removibles

    relaciones_insumos = (
        RecetaInsumo.objects
        .filter(
            idreceta__idproducto=producto,
            es_removible=True,
            idinsumo__isnull=False,
        )
        .select_related("idinsumo")
    )

    insumos_validos = {
        str(relacion.idinsumo.pk): relacion.idinsumo
        for relacion in relaciones_insumos
        if relacion.idinsumo
    }

    insumos_quitados_ids = []

    for clave, valor in request.POST.items():
        if not clave.startswith("sin_insumo_"):
            continue

        insumo_id = clave[len("sin_insumo_"):]

        if (
            insumo_id not in insumos_validos
            or str(valor) != insumo_id
        ):
            return _volver_a_detalle(
                request,
                producto,
                "Se recibió un ingrediente no válido."
            )

        insumo = insumos_validos[insumo_id]

        if insumo_id not in insumos_quitados_ids:
            insumos_quitados_ids.append(insumo_id)

            detalle_opciones.append(
                f"Sin {insumo.nombreinsumo}"
            )

    # 5. Construir una identidad estable de configuración

    opciones_seleccionadas.sort()
    insumos_quitados_ids.sort()

    configuracion = {
        "producto_id": str(producto.idproducto),
        "opciones": opciones_seleccionadas,
        "extras": extras_seleccionados,
        "insumos": insumos_quitados_ids,
    }

    firma = hashlib.sha256(
        json.dumps(
            configuracion,
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:20]

    item_id = f"{producto.idproducto}_{firma}"

    cantidad_item = (
        int(carrito[edit_id].get("cantidad", 1))
        if edit_id
        else 1
    )

    if cantidad_item < 1:
        cantidad_item = 1

    precio_unitario = _precio_dos_decimales(precio_unitario)

    nuevo_item = {
        "producto_id": producto.idproducto,
        "nombre": producto.nombre,
        "imagen": producto.imagen.url if producto.imagen else "",
        "precio_unitario": float(precio_unitario),
        "cantidad": cantidad_item,
        "subtotal": float(
            _precio_dos_decimales(
                precio_unitario * cantidad_item
            )
        ),
        "detalles": detalle_opciones,
        "opciones_ids": opciones_seleccionadas,
        "extras_ids": extras_seleccionados,
        "insumos_quitados_ids": insumos_quitados_ids,
    }

    # No modificar el carrito hasta validar toda la configuración.
    if edit_id:
        carrito.pop(edit_id, None)

    if item_id in carrito:
        carrito[item_id]["cantidad"] = (
            int(carrito[item_id].get("cantidad", 1))
            + cantidad_item
        )

        carrito[item_id]["subtotal"] = float(
            _precio_dos_decimales(
                _decimal_seguro(
                    carrito[item_id]["precio_unitario"]
                )
                * carrito[item_id]["cantidad"]
            )
        )
    else:
        carrito[item_id] = nuevo_item

    request.session["carrito"] = carrito
    request.session.modified = True
    request.session.pop("edit_item_id", None)

    return redirect("ver_carrito")



def editar_item_carrito(request, item_id):
    carrito = request.session.get('carrito', {})

    if item_id in carrito:
        request.session['edit_item_id'] = item_id
        return redirect(
            'detalleProducto',
            idproducto=carrito[item_id]['producto_id'],
        )

    return redirect('ver_carrito')

@ensure_csrf_cookie
def ver_carrito(request):
    # Al volver al carrito se descarta el estado de edición.
    if request.session.pop('edit_item_id', None) is not None:
        request.session.modified = True

    carrito = request.session.get('carrito', {})
    # DEF-002, DEF-010, DEF-011: Depurar carrito y reflejar precios actuales vigentes
    carrito, quitados = _depurar_carrito(request, carrito)
    if quitados:
        messages.warning(request, _aviso_productos_quitados(quitados))

    total_carrito = sum(item.get('subtotal', 0) for item in carrito.values())

    return render(request, 'publico/carrito.html', {
        'carrito': carrito,
        'total_carrito': total_carrito,
        'negocio': Negocio.objects.first(),
        'instagram': obtener_instagram(),
        'estado_local': local_estado(),
    })


def actualizar_cantidad_carrito(request, item_id, accion):
    carrito = request.session.get('carrito', {})

    if item_id in carrito:
        if accion == 'aumentar':
            estado = local_estado()
            if not estado.get('abierto', True):
                messages.error(
                    request,
                    "En este momento el negocio está cerrado. No es posible agregar productos al carrito."
                )
                return redirect('ver_carrito')
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
        request.session['carrito'] = carrito
        request.session.modified = True

    # DEF-004: Recalcular subtotales, totales y revalidar promociones en sesión
    if not carrito:
        request.session.pop('promocion_id', None)
        request.session.pop('codigo_promocion', None)
        request.session.pop('descuento_promocion', None)
    else:
        for it in carrito.values():
            try:
                pu = float(it.get('precio_unitario', 0))
                cnt = int(it.get('cantidad', 1))
                it['subtotal'] = pu * cnt
            except (ValueError, TypeError):
                pass

        promo_id = request.session.get('promocion_id')
        if promo_id:
            promo = Promocion.objects.filter(pk=promo_id, activo=1).first()
            if promo and promocion_es_valida(promo):
                res = calcular_total_pedido(carrito, promo)
                if res['descuento'] > 0:
                    request.session['descuento_promocion'] = str(res['descuento'])
                else:
                    request.session.pop('promocion_id', None)
                    request.session.pop('codigo_promocion', None)
                    request.session.pop('descuento_promocion', None)
            else:
                request.session.pop('promocion_id', None)
                request.session.pop('codigo_promocion', None)
                request.session.pop('descuento_promocion', None)

    request.session['carrito'] = carrito
    request.session.modified = True

    if es_peticion_ajax(request):
        total_carrito = sum(item.get('subtotal', 0) for item in carrito.values())
        return JsonResponse({
            'status': 'ok',
            'total_carrito': float(total_carrito),
            'cantidad_items': len(carrito),
        })

    return redirect('ver_carrito')


# 3. LÓGICA DE PROMOCIONES

def promocion_es_valida(promocion):
    if not promocion:
        return False

    if promocion.activo != 1:
        return False

    hoy = timezone.localdate()

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
    """Devuelve (descuento, mensaje) según el tipo de beneficio."""
    if not promocion:
        return Decimal('0.00'), ''

    if not promocion_es_valida(promocion):
        return Decimal('0.00'), 'La promoción no está vigente.'

    productos_validos = obtener_productos_promocion(promocion)

    if not productos_validos:
        return Decimal('0.00'), 'La promoción no tiene productos asociados.'

    # Una entrada por unidad, para poder aplicar promos tipo 2x1 o 3x2.
    unidades = []
    subtotal_elegible = Decimal('0.00')

    for item in carrito.values():
        producto_id = item.get('producto_id')

        if producto_id is None:
            continue

        try:
            producto_id = int(producto_id)
        except (TypeError, ValueError):
            continue

        if producto_id not in productos_validos:
            continue

        try:
            cantidad = int(item.get('cantidad', 0))
        except (TypeError, ValueError):
            cantidad = 0

        if cantidad <= 0:
            continue

        try:
            precio_unitario = Decimal(str(item.get('precio_unitario', 0)))
        except Exception:
            precio_unitario = Decimal('0.00')

        if precio_unitario <= 0:
            continue

        subtotal_elegible += precio_unitario * cantidad
        unidades.extend([precio_unitario] * cantidad)

    if not unidades:
        return (
            Decimal('0.00'),
            'La promoción no aplica a los productos del carrito.',
        )

    tipo = (promocion.tipobeneficio.codigo or '').upper().strip() if promocion.tipobeneficio else ''
    comportamiento = (getattr(promocion.tipobeneficio, 'comportamiento', '') or '').upper().strip()
    valor = promocion.valor or Decimal('0.00')
    descuento = Decimal('0.00')
    mensaje = ''

    if tipo in ('2X1', '2_X_1') and len(unidades) < 2:
        return (
            Decimal('0.00'),
            'La promoción 2 x 1 requiere 2 unidades: agregá 1 unidad más.',
        )

    if tipo in ('3X2', '3_X_2') and len(unidades) < 3:
        faltan = 3 - len(unidades)
        return (
            Decimal('0.00'),
            'La promoción 3 x 2 requiere 3 unidades: '
            f'agregá {faltan} unidad{"es" if faltan > 1 else ""} más.',
        )

    if tipo in ('2X1', '2_X_1'):
        unidades.sort()
        descuento = sum(unidades[:len(unidades) // 2], Decimal('0.00'))
        mensaje = 'Promoción 2 x 1 aplicada.'

    elif tipo in ('3X2', '3_X_2'):
        unidades.sort()
        descuento = sum(unidades[:len(unidades) // 3], Decimal('0.00'))
        mensaje = 'Promoción 3 x 2 aplicada.'

    elif tipo in ('PRODUCTO_GRATIS', 'REGALO'):
        descuento = min(unidades)
        mensaje = 'Producto gratis aplicado.'

    # DEF-007: Reconocer descuentos porcentuales según código o comportamiento del tipo de beneficio
    elif tipo in ('DESCUENTO_PORCENTAJE', 'PORCENTAJE') or comportamiento == 'PORCENTAJE':
        porcentaje = max(Decimal('0.00'), min(valor, Decimal('100.00')))
        descuento = subtotal_elegible * porcentaje / Decimal('100')
        mensaje = f'Descuento del {porcentaje}% aplicado.'

    elif tipo in ('DESCUENTO_FIJO', 'MONTO_FIJO', 'FIJO') or comportamiento == 'MONTO_FIJO':
        descuento = min(valor, subtotal_elegible)
        mensaje = f'Descuento de ${descuento} aplicado.'

    elif comportamiento == 'SIN_VALOR':
        descuento = min(unidades)
        mensaje = 'Beneficio aplicado.'

    else:
        return Decimal('0.00'), 'Tipo de promoción no válido.'

    descuento = max(Decimal('0.00'), min(descuento, subtotal_elegible))
    descuento = descuento.quantize(Decimal('0.01'))

    return descuento, mensaje


def calcular_total_pedido(carrito, promocion=None):
    subtotal = Decimal('0.00')

    for item in carrito.values():
        try:
            cantidad = int(item.get('cantidad', 0))
        except (TypeError, ValueError):
            cantidad = 0

        try:
            precio_unitario = Decimal(str(item.get('precio_unitario', 0)))
        except Exception:
            precio_unitario = Decimal('0.00')

        if cantidad > 0:
            subtotal += precio_unitario * cantidad

    descuento, mensaje = calcular_descuento_promocion(carrito, promocion)

    total = max(Decimal('0.00'), subtotal - descuento)

    return {
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'descuento': descuento.quantize(Decimal('0.01')),
        'total': total.quantize(Decimal('0.01')),
        'mensaje': mensaje,
    }


@require_POST
def aplicar_promocion(request):
    codigo = request.POST.get('codigo_promocion', '').strip().upper()

    if not codigo:
        return JsonResponse({
            'ok': False,
            'mensaje': 'Ingresá una palabra clave.',
        })

    try:
        promocion = Promocion.objects.get(
            palabraclave__iexact=codigo,
            activo=1,
        )
    except Promocion.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'mensaje': 'La promoción no existe o no está activa.',
        })

    if not promocion_es_valida(promocion):
        return JsonResponse({
            'ok': False,
            'mensaje': 'La promoción no está vigente.',
        })

    carrito = request.session.get('carrito', {})

    if not carrito:
        return JsonResponse({
            'ok': False,
            'mensaje': 'El carrito está vacío.',
        })

    resultado = calcular_total_pedido(carrito, promocion)

    if resultado['descuento'] <= Decimal('0.00'):
        return JsonResponse({
            'ok': False,
            'mensaje': (
                resultado['mensaje'] or 'La promoción no aplica al carrito.'
            ),
        })

    request.session['promocion_id'] = promocion.idpromocion
    request.session['codigo_promocion'] = codigo
    request.session['descuento_promocion'] = str(resultado['descuento'])
    request.session.modified = True

    return JsonResponse({
        'ok': True,
        'promocion_id': promocion.idpromocion,
        'codigo': codigo,
        'descuento': float(resultado['descuento']),
        'subtotal': float(resultado['subtotal']),
        'total': float(resultado['total']),
        'mensaje': resultado['mensaje'],
    })


# 4. CHECKOUT Y PEDIDOS

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


def calcular_consumo_insumos(carrito):
    """Devuelve el consumo total de insumos del carrito (recetas base y opciones)."""
    return calcular_consumo_carrito(carrito)


def _producto_disponible(producto):
    """False si el producto está marcado como no disponible/inactivo/eliminado/oculto."""
    if not producto:
        return False

    # DEF-002 / DEF-010: Validar estado del producto según EstadoProducto
    if getattr(producto, 'idestadoproducto_id', None) in ESTADOS_NO_VISIBLES:
        return False

    if hasattr(producto, 'idestadoproducto') and producto.idestadoproducto:
        if producto.idestadoproducto_id != ESTADO_ACTIVO:
            return False

    for nombre_campo in ('disponible', 'activo', 'habilitado', 'visible'):
        if hasattr(producto, nombre_campo):
            if getattr(producto, nombre_campo) is False:
                return False

    return True


def _depurar_carrito(request, carrito):
    """Revalida el carrito contra la BD: quita lo no disponible, actualiza
    precios, nombres y detalles. Devuelve (carrito, nombres_quitados)."""
    if not carrito:
        return carrito, []

    antes = json.dumps(carrito, sort_keys=True, default=str)

    for item in carrito.values():
        extras = item.get('extras_ids') or {}
        if isinstance(extras, list):
            extras = {str(k): 1 for k in extras}
        item['extras_ids'] = {str(k): v for k, v in extras.items()}

    ids_prod, ids_opc, ids_ext, ids_ins = set(), set(), set(), set()
    for item in carrito.values():
        if item.get('producto_id') is not None:
            ids_prod.add(item['producto_id'])
        ids_opc.update(str(x) for x in item.get('opciones_ids') or [])
        ids_ext.update(item['extras_ids'].keys())
        ids_ins.update(str(x) for x in item.get('insumos_quitados_ids') or [])

    productos = {str(p.pk): p for p in Producto.objects.filter(pk__in=ids_prod)}
    opciones = {
        str(o.pk): o
        for o in Opcion.objects.filter(pk__in=ids_opc).select_related('idgrupo')
    }
    extras_bd = {str(e.pk): e for e in Extras.objects.filter(pk__in=ids_ext)}
    insumos = {str(i.pk): i for i in Insumo.objects.filter(pk__in=ids_ins)}

    vigente, quitados = {}, []

    for clave, item in carrito.items():
        nombre_previo = item.get('nombre') or 'Producto'
        producto = productos.get(str(item.get('producto_id')))

        if producto is None or not _producto_disponible(producto):
            quitados.append(nombre_previo)
            continue

        precio = _decimal_seguro(producto.precio)
        detalles = []
        valido = True

        for oid in sorted(str(x) for x in item.get('opciones_ids') or []):
            opc = opciones.get(oid)
            if opc is None:
                valido = False
                break
            precio += _decimal_seguro(opc.precioadicional)
            grupo = opc.idgrupo.nombre if opc.idgrupo else 'Opción'
            detalles.append(f"{grupo}: {opc.nombre}")

        if valido:
            for eid, cant in sorted(item['extras_ids'].items()):
                ext = extras_bd.get(str(eid))
                if ext is None:
                    valido = False
                    break
                try:
                    cant = max(1, int(cant))
                except (TypeError, ValueError):
                    cant = 1
                precio += _decimal_seguro(ext.precio) * cant
                detalles.append(f"Extra: {ext.nombre} (x{cant})")

        if not valido:
            quitados.append(nombre_previo)
            continue

        for iid in sorted(str(x) for x in item.get('insumos_quitados_ids') or []):
            ins = insumos.get(iid)
            if ins:
                detalles.append(f"Sin {ins.nombreinsumo}")

        try:
            cantidad = max(1, int(item.get('cantidad', 1) or 1))
        except (TypeError, ValueError):
            cantidad = 1

        precio = _precio_dos_decimales(precio)
        item['nombre'] = producto.nombre
        item['detalles'] = detalles
        item['cantidad'] = cantidad
        item['precio_unitario'] = float(precio)
        item['subtotal'] = float(_precio_dos_decimales(precio * cantidad))
        if producto.imagen:
            item['imagen'] = producto.imagen.url

        vigente[clave] = item

    if json.dumps(vigente, sort_keys=True, default=str) != antes:
        request.session['carrito'] = vigente
        request.session.modified = True

    return vigente, quitados


def _aviso_productos_quitados(nombres):
    if not nombres:
        return ''

    if len(nombres) == 1:
        return f'Quitamos "{nombres[0]}" de tu pedido porque ya no está disponible.'

    listado = ', '.join(f'"{n}"' for n in nombres)
    return (
        'Quitamos de tu pedido los siguientes productos porque ya no están '
        f'disponibles: {listado}.'
    )


def _json_sin_cache(datos, status=200):
    """JsonResponse que el navegador nunca guarda en caché (para el estado en vivo)."""
    respuesta = JsonResponse(datos, status=status)
    respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    respuesta['Pragma'] = 'no-cache'
    respuesta['Vary'] = 'X-Requested-With, Accept'
    return respuesta


def _items_para_json(carrito):
    """Items del carrito en un formato seguro para JSON."""
    items = []

    for item_id, item in zip(carrito.keys(), _items_checkout(carrito)):
        detalles = item.get('detalles')

        items.append({
            'id': str(item_id),
            'cantidad': item.get('cantidad', 1),
            'nombre': item.get('nombre', ''),
            'detalles': list(detalles) if isinstance(detalles, (list, tuple)) else [],
            'precio_unitario': f"{item['precio_unitario']:.2f}",
            'subtotal': f"{item['subtotal']:.2f}",
        })

    return items


# Reemplaza la vista procesar_checkout completa en views.py.
# Requiere que ya existan en views.py (las del mensaje anterior):
#   local_ventanas_entrega, error_horario_entrega, _items_para_json (versión nueva)


CHECKOUT_BLOQUEO_SEGUNDOS = 60


def _checkout_en_proceso(request):
    """True si hay otro envío del checkout en curso (con vencimiento)."""
    marca = request.session.get('checkout_procesando')

    if not marca:
        return False

    try:
        return (timezone.now().timestamp() - float(marca)) < CHECKOUT_BLOQUEO_SEGUNDOS
    except (TypeError, ValueError):
        # Valor viejo (True): se considera vencido.
        return False


def _checkout_liberar(request):
    request.session.pop('checkout_procesando', None)
    request.session.modified = True


def procesar_checkout(request):
    info_estado = local_estado()
    negocio_abierto = info_estado.get('abierto', True)

    mensaje_cerrado = (
        'El negocio está cerrado en este momento. '
        'Podrás realizar tu pedido cuando vuelva a abrir.'
    )

    es_consulta_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or (
            request.method == 'GET'
            and 'application/json' in request.META.get('HTTP_ACCEPT', '')
        )
    )

    carrito = request.session.get('carrito', {})

    # Quitar productos eliminados o no disponibles antes de calcular nada.
    carrito, productos_quitados = _depurar_carrito(request, carrito)
    avisos = [_aviso_productos_quitados(productos_quitados)] if productos_quitados else []

    total_carrito = sum(
        (
            Decimal(str(i.get('subtotal', 0)))
            for i in carrito.values()
        ),
        Decimal('0.00'),
    )

    medios_pago = list(
        MedioPago.objects.values('idmediopago', 'nombremetodo')
    )

    zonas_entrega = list(
        ZonasEntrega.objects.values('idzona', 'nombre', 'costoenvio')
    )

    # Límite real del comentario según el campo del modelo (fallback: 500).
    comentario_max = (
        Pedido._meta.get_field('justificacioncancelacion').max_length or 500
    )

    # Horarios en los que se puede pedir la entrega (según el horario de atención).
    entrega = local_ventanas_entrega(info_estado)

    contexto = {
        'medios_pago': medios_pago,
        'zonas_entrega': zonas_entrega,
        'total_carrito': total_carrito,
        'comentario_max': comentario_max,
        'carrito_items': _items_checkout(carrito),
        'items_json': _items_para_json(carrito),
        'entrega': entrega,
        'avisos': avisos,
        'negocio_abierto': negocio_abierto,
        'mensaje_negocio': (
            info_estado.get('mensaje', '')
            if negocio_abierto
            else mensaje_cerrado
        ),
    }

    # Consulta AJAX: devuelve el estado actual sin redirigir.
    if es_consulta_json:
        estado_checkout = {
            'mensaje_negocio': contexto['mensaje_negocio'],
            'quitados': productos_quitados,
            'aviso_productos': avisos[0] if avisos else '',
            'carrito_items': contexto['items_json'],
            'carrito_vacio': not carrito,
            'entrega': entrega,
            'zonas_entrega': zonas_entrega,
        }

        if not negocio_abierto:
            return _json_sin_cache(
                {
                    'status': 'error',
                    'mensaje': mensaje_cerrado,
                    'cerrado': True,
                    'total_carrito': str(total_carrito),
                    **estado_checkout,
                },
                status=403,
            )

        return _json_sin_cache({
            'status': 'success',
            'total_carrito': str(total_carrito),
            'medios_pago': medios_pago,
            'zonas_entrega': zonas_entrega,
            'cerrado': False,
            **estado_checkout,
        })

    # GET: mostrar el formulario.
    if request.method != 'POST':
        return render(
            request,
            'publico/checkout.html',
            {
                **contexto,
                'total_estimado': total_carrito,
                'errores': {'codigo_promocion': ''},
                'codigo_promocion': '',
                'datos_previos': {},
                'hay_datos_previos': False,
                'coord_lat': '',
                'coord_lng': '',
                'error_telefono': '',
                'error_medio_pago': '',
                'error_promocion': '',
                'descuento_promocion': Decimal('0.00'),
                'objeto_promocion': None,
            },
        )

    # POST: confirmar el pedido.

    if _checkout_en_proceso(request):
        if request.session.get('whatsapp_url'):
            return redirect('pedido_exitoso')
        return redirect('ver_carrito')

    request.session['checkout_procesando'] = timezone.now().timestamp()
    request.session.modified = True

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
    # El navegador envía cada salto de línea como \r\n (2 caracteres),
    # aunque el textarea cuente 1. Se normaliza para no pasarse del límite.
    comentario = campo('comentario').replace('\r\n', '\n').replace('\r', '\n')
    id_medio_pago = request.POST.get('medio_pago')

    errores = {'codigo_promocion': ''}
    error_promocion = ''
    objeto_promocion = None
    descuento_promocion = Decimal('0.00')

    # Si se cerró el negocio, no procesar ni crear el pedido.
    if not negocio_abierto:
        _checkout_liberar(request)
        errores['negocio'] = mensaje_cerrado

        return render(
            request,
            'publico/checkout.html',
            {
                **contexto,
                'total_estimado': total_carrito,
                'datos_previos': request.POST,
                'hay_datos_previos': True,
                'errores': errores,
                'error_telefono': '',
                'error_medio_pago': '',
                'error_promocion': '',
                'descuento_promocion': Decimal('0.00'),
                'objeto_promocion': None,
                'codigo_promocion': codigo_promo,
            },
        )

    # Si se quitaron productos al confirmar, no se crea el pedido:
    # se muestra el checkout actualizado para que el cliente revise el total.
    if productos_quitados:
        _checkout_liberar(request)

        if not carrito:
            messages.warning(request, avisos[0])
            return redirect('ver_carrito')

        return render(
            request,
            'publico/checkout.html',
            {
                **contexto,
                'total_estimado': total_carrito,
                'datos_previos': request.POST,
                'hay_datos_previos': True,
                'errores': {'codigo_promocion': ''},
                'coord_lat': campo('coord_lat'),
                'coord_lng': campo('coord_lng'),
                'error_telefono': '',
                'error_medio_pago': '',
                'error_promocion': '',
                'descuento_promocion': Decimal('0.00'),
                'objeto_promocion': None,
                'codigo_promocion': codigo_promo,
            },
        )

    # Si el carrito está vacío, volver al carrito.
    if not carrito:
        _checkout_liberar(request)

        # Envío duplicado: el pedido ya se procesó y el carrito se vació,
        # así que se lleva al cliente a la pantalla de éxito.
        if request.session.get('whatsapp_url'):
            return redirect('pedido_exitoso')

        messages.error(request, 'Tu carrito está vacío.')
        return redirect('ver_carrito')

    # Validación del nombre.
    if not nombre:
        errores['nombre'] = 'Ingresá tu nombre.'
    elif not 2 <= len(nombre) <= 100:
        errores['nombre'] = (
            'El nombre debe tener entre 2 y 100 caracteres.'
        )

    # Validación del apellido.
    if not apellido:
        errores['apellido'] = 'Ingresá tu apellido.'
    elif not 2 <= len(apellido) <= 100:
        errores['apellido'] = (
            'El apellido debe tener entre 2 y 100 caracteres.'
        )

    # Validación del teléfono.
    telefono_limpio = limpiar_numero_telefono(telefono)

    if not es_telefono_cliente_valido(telefono_limpio):
        errores['telefono'] = (
            'Ingresá un teléfono válido '
            '(solo números, entre 8 y 13 dígitos).'
        )

    # Validación de la dirección.
    if not calle:
        errores['calle'] = 'Ingresá la calle.'
    elif len(calle) > 150:
        errores['calle'] = 'La calle es demasiado larga.'

    if not numero:
        errores['numero'] = 'Ingresá el número de la calle.'
    elif len(numero) > 20:
        errores['numero'] = 'El número de calle es demasiado largo.'

    # Validación del comentario.
    if len(comentario) > comentario_max:
        errores['comentario'] = (
            f'El comentario no puede superar los {comentario_max} caracteres '
            f'(escribiste {len(comentario)}).'
        )

    # Validación del método de pago.
    medio_pago = None

    if not id_medio_pago:
        errores['medio_pago'] = 'Seleccioná un método de pago.'
    else:
        medio_pago = MedioPago.objects.filter(
            pk=id_medio_pago
        ).first()

        if medio_pago is None:
            errores['medio_pago'] = (
                'Seleccioná un método de pago válido.'
            )

    # Validación del horario de entrega (dentro del horario de atención,
    # con margen antes del cierre).
    horario_deseado = None

    if horario_entrega:
        try:
            horario_deseado = datetime.strptime(
                horario_entrega,
                '%H:%M',
            ).time()
        except ValueError:
            errores['horario_entrega'] = (
                'El horario de entrega no es válido.'
            )
        else:
            error_horario = error_horario_entrega(horario_deseado, entrega)

            if error_horario:
                errores['horario_entrega'] = error_horario

    # Cálculo y análisis geográfico y automático de zonas de entrega
    id_zona = campo('id_zona')
    coord_lat = campo('coord_lat')
    coord_lng = campo('coord_lng')

    # La ubicación marcada debe estar dentro de la zona de entrega (CABA).
    # Es una red de seguridad gruesa: el rectángulo contiene a toda la ciudad,
    # así que solo rechaza ubicaciones claramente fuera.
    # Formato: (lat_min, lat_max, lng_min, lng_max)
    caba_bbox = (-34.7055, -34.5265, -58.5315, -58.3350)

    if coord_lat and coord_lng:
        try:
            lat_valor = float(coord_lat.replace(',', '.'))
            lng_valor = float(coord_lng.replace(',', '.'))
        except ValueError:
            errores['direccion'] = 'La ubicación marcada no es válida.'
        else:
            dentro_de_zona = (
                caba_bbox[0] <= lat_valor <= caba_bbox[1]
                and caba_bbox[2] <= lng_valor <= caba_bbox[3]
            )
            if not dentro_de_zona:
                errores['direccion'] = (
                    'La dirección marcada está fuera de nuestra zona de entrega. '
                    'Solo realizamos entregas en la Ciudad Autónoma de Buenos Aires.'
                )

    from core.geo_zonas import detectar_zona_entrega

    resultado_zona = detectar_zona_entrega(
        calle=calle,
        numero=numero,
        localidad=localidad,
        lat=coord_lat,
        lon=coord_lng,
        id_zona_sugerida=id_zona if (id_zona and id_zona != 'otro') else None,
    )

    zona = resultado_zona.get('zona')
    costo_envio = resultado_zona.get('costoenvio', Decimal('0.00'))
    costo_envio_texto = resultado_zona.get('costoenvio_texto', 'A coordinar')
    localidad_guardar = (
        resultado_zona.get('localidad_guardar')
        or (localidad or 'A coordinar con el vendedor')
    )
    zona_seleccionada_id = resultado_zona.get('idzona')

    # Validación de la promoción.
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
                calcular_descuento_promocion(
                    carrito,
                    objeto_promocion,
                )
            )

            if descuento_promocion <= 0:
                error_promocion = (
                    mensaje_promocion
                    or (
                        'La promoción no aplica a los productos '
                        'de tu carrito.'
                    )
                )

        if error_promocion:
            errores['codigo_promocion'] = error_promocion

    # Si hay errores, mantener los datos en el checkout.
    if any(errores.values()):
        _checkout_liberar(request)

        total_estimado = max(
            Decimal('0.00'),
            total_carrito - descuento_promocion + costo_envio,
        )

        return render(
            request,
            'publico/checkout.html',
            {
                **contexto,
                'total_estimado': total_estimado,
                'costo_envio': costo_envio,
                'costo_envio_texto': costo_envio_texto,
                'zona_seleccionada_id': zona_seleccionada_id,
                'resultado_zona': resultado_zona,
                'coord_lat': coord_lat,
                'coord_lng': coord_lng,
                'datos_previos': request.POST,
                'hay_datos_previos': True,
                'errores': errores,
                'error_telefono': errores.get('telefono', ''),
                'error_medio_pago': errores.get('medio_pago', ''),
                'error_promocion': error_promocion,
                'descuento_promocion': descuento_promocion,
                'objeto_promocion': objeto_promocion,
                'codigo_promocion': codigo_promo,
            },
        )

    telefono = telefono_limpio

    total_general = max(
        Decimal('0.00'),
        total_carrito - descuento_promocion + costo_envio,
    )

    consumo_insumos = calcular_consumo_carrito(carrito)

    # Verificación previa del stock.
    stock_ok, errores_stock = verificar_stock_disponible(
        consumo_insumos
    )

    if not stock_ok:
        _checkout_liberar(request)

        for err in errores_stock:
            messages.error(request, err)

        return redirect('ver_carrito')

    try:
        with transaction.atomic():
            # Revalidar el estado inmediatamente antes de crear el pedido.
            info_confirmacion = local_estado()

            if not info_confirmacion.get('abierto', True):
                raise ValueError(
                    'El negocio acaba de cerrar. '
                    'Tu pedido no fue confirmado. '
                    'Podés volver a intentarlo cuando abra.'
                )

            if horario_deseado is not None:
                error_horario_final = error_horario_entrega(horario_deseado)

                if error_horario_final:
                    raise ValueError(error_horario_final)

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
                localidad=localidad_guardar,
            )

            estado_inicial = get_object_or_404(
                EstadoPedido,
                pk=1,
            )

            pedido = Pedido.objects.create(
                idcliente=cliente,
                idmediopago=medio_pago,
                idestadopedido=estado_inicial,
                idpromocion=(
                    objeto_promocion.idpromocion
                    if objeto_promocion
                    else None
                ),
                nombrepromocion=(
                    (objeto_promocion.palabraclave or '')[:100] or None
                    if objeto_promocion
                    else None
                ),
                descuentopromocion=(
                    descuento_promocion if objeto_promocion else None
                ),
                horarioentregadeseado=horario_deseado,
                total=total_general,
                justificacioncancelacion=(
                    comentario[:comentario_max] if comentario else None
                ),
            )

            # Revalidación completa del carrito justo antes de confirmar.
            for item in carrito.values():
                producto = Producto.objects.filter(
                    pk=item.get('producto_id')
                ).first()

                if not producto or not _producto_disponible(producto):
                    raise ValueError(
                        f"El producto '{item.get('nombre', 'Producto')}' "
                        'ya no está disponible o fue eliminado. '
                        'Revisá tu carrito.'
                    )

                cantidad = item.get('cantidad', 1) or 1
                subtotal_item = Decimal(
                    str(item.get('subtotal', 0))
                )
                detalles = item.get('detalles')

                # Longitud máxima en observaciones de DetallePedido (250 chars).
                detalles_txt = (
                    ', '.join(detalles) if isinstance(detalles, list) else ''
                )
                if len(detalles_txt) > 250:
                    detalles_txt = detalles_txt[:247] + '...'

                DetallePedido.objects.create(
                    idpedido=pedido,
                    idproducto=producto,
                    cantidad=cantidad,
                    preciounitario=subtotal_item / cantidad,
                    observaciones=detalles_txt,
                )

            descontar_stock_pedido(
                pedido,
                consumo_insumos,
            )

    except ValueError as e:
        _checkout_liberar(request)

        # Si cerró durante la confirmación, quedarse en checkout.
        info_estado = local_estado()
        negocio_abierto = info_estado.get('abierto', True)

        if not negocio_abierto:
            contexto['negocio_abierto'] = False
            contexto['mensaje_negocio'] = (
                info_estado.get('mensaje', '') or mensaje_cerrado
            )

            messages.error(request, str(e))

            return render(
                request,
                'publico/checkout.html',
                {
                    **contexto,
                    'total_estimado': total_general,
                    'datos_previos': request.POST,
                    'hay_datos_previos': True,
                    'errores': {
                        'codigo_promocion': '',
                        'negocio': str(e),
                    },
                    'error_telefono': '',
                    'error_medio_pago': '',
                    'error_promocion': '',
                    'descuento_promocion': descuento_promocion,
                    'objeto_promocion': objeto_promocion,
                    'codigo_promocion': codigo_promo,
                },
            )

        # El horario dejó de ser válido durante la confirmación:
        # se vuelve al checkout con el error marcado en ese campo.
        if horario_deseado is not None and error_horario_entrega(horario_deseado):
            contexto['entrega'] = local_ventanas_entrega(info_estado)

            return render(
                request,
                'publico/checkout.html',
                {
                    **contexto,
                    'total_estimado': total_general,
                    'costo_envio': costo_envio,
                    'costo_envio_texto': costo_envio_texto,
                    'zona_seleccionada_id': zona_seleccionada_id,
                    'resultado_zona': resultado_zona,
                    'coord_lat': coord_lat,
                    'coord_lng': coord_lng,
                    'datos_previos': request.POST,
                    'hay_datos_previos': True,
                    'errores': {
                        'codigo_promocion': '',
                        'horario_entrega': str(e),
                    },
                    'error_telefono': '',
                    'error_medio_pago': '',
                    'error_promocion': '',
                    'descuento_promocion': descuento_promocion,
                    'objeto_promocion': objeto_promocion,
                    'codigo_promocion': codigo_promo,
                },
            )

        messages.error(request, str(e))
        return redirect('ver_carrito')

    except StockInsuficienteError as e:
        _checkout_liberar(request)
        messages.error(request, str(e))
        return redirect('ver_carrito')

    # Pedido creado: preparar mensaje para WhatsApp.
    # Los emojis van como escapes Unicode para no depender de la
    # codificación del archivo.
    E_BURGER = '\U0001F354'
    E_CLIENTE = '\U0001F464'
    E_TEL = '\U0001F4DE'
    E_PIN = '\U0001F4CD'
    E_RELOJ = '\U0001F552'
    E_TICKET = '\U0001F9FE'
    E_PROMO = '\U0001F381'
    E_MOTO = '\U0001F6F5'
    E_TOTAL = '\U0001F4B0'
    E_PAGO = '\U0001F4B3'
    E_NOTA = '\U0001F4AC'
    E_CHECK = '\u2705'
    LINEA = '\u2501' * 16

    direccion_txt = f'{calle} {numero}'
    if piso:
        direccion_txt += f' (Piso/Depto: {piso})'

    lineas = [
        f'\u00A1Hola! Acabo de realizar un pedido desde la web {E_BURGER}',
        f'*Pedido N\u00B0 {pedido.pk}*',
        LINEA,
        '',
        f'{E_CLIENTE} *Mis datos*',
        f'{nombre} {apellido}',
        f'{E_TEL} {telefono}',
        '',
        f'{E_PIN} *Dirección de entrega*',
        direccion_txt,
        f'{localidad_guardar}',
    ]

    if horario_entrega:
        lineas.append(f'{E_RELOJ} Horario de entrega deseado: {horario_entrega} hs')

    lineas += ['', f'{E_TICKET} *Mi pedido*']

    for item in carrito.values():
        subtotal = Decimal(str(item.get('subtotal', 0)))

        lineas.append(
            f'\u25AA {item.get("cantidad")}x {item.get("nombre")} '
            f'\u2014 *${subtotal:.2f}*'
        )

        for detalle in item.get('detalles', []):
            lineas.append(f'     \u21B3 _{detalle}_')

    lineas += ['', LINEA]
    lineas.append(f'Subtotal: ${total_carrito:.2f}')

    # Línea de promoción con palabra clave o descripción amigable.
    promo_obj = objeto_promocion
    if not promo_obj and getattr(pedido, 'idpromocion', None):
        promo_obj = Promocion.objects.filter(pk=pedido.idpromocion).first()

    if promo_obj and descuento_promocion > 0:
        desc_amigable = getattr(promo_obj, 'descripcion_amigable', '')
        clave = getattr(promo_obj, 'palabraclave', '') or codigo_promo
        if clave and desc_amigable:
            texto_promo = f"{clave} ({desc_amigable})"
        elif clave:
            texto_promo = clave
        elif desc_amigable:
            texto_promo = desc_amigable
        else:
            texto_promo = f"Promoción #{promo_obj.pk}"
        lineas.append(
            f'{E_PROMO} Promo {texto_promo}: -${descuento_promocion:.2f}'
        )

    lineas.append(f'{E_MOTO} Envío: {costo_envio_texto}')
    lineas.append(LINEA)
    lineas.append(f'{E_TOTAL} *Total a pagar: ${total_general:.2f}*')
    lineas.append(f'{E_PAGO} Pago con: *{medio_pago.nombremetodo}*')

    if comentario:
        lineas += ['', f'{E_NOTA} *Aclaraciones:*', f'_{comentario}_']

    lineas += ['', f'Quedo atento a la confirmaci\u00F3n. \u00A1Gracias! {E_CHECK}']

    mensaje = '\n'.join(lineas)

    negocio = Negocio.objects.first()

    numero_whatsapp = limpiar_numero_telefono(
        str(negocio.telefono)
        if negocio and negocio.telefono
        else ''
    )

    # El pedido ya está creado: vaciar el carrito y liberar el bloqueo.
    request.session.pop('carrito', None)
    for clave_promo in ('promocion_id', 'codigo_promocion', 'descuento_promocion'):
        request.session.pop(clave_promo, None)
    _checkout_liberar(request)

    if not numero_whatsapp:
        logger.warning(
            'El negocio no tiene un número de WhatsApp configurado.'
        )
        return redirect('menu')

    request.session['whatsapp_url'] = (
        f'https://api.whatsapp.com/send?phone={numero_whatsapp}'
        f'&text={quote(mensaje, safe="", encoding="utf-8")}'
    )
    request.session['limpiar_checkout'] = True
    request.session.modified = True

    return redirect('pedido_exitoso')


def pedido_exitoso(request):
    # Solo se llega acá después de confirmar un pedido en el checkout.
    if not request.session.get('whatsapp_url'):
        return redirect('menu')

    limpiar_checkout = request.session.pop('limpiar_checkout', False)

    return render(request, 'publico/pedidoExitoso.html', {
        'negocio': Negocio.objects.first(),
        'whatsapp_url': request.session.get('whatsapp_url'),
        'limpiar_checkout': limpiar_checkout,
    })


# 5. PANEL - INICIO Y PEDIDOS

@panel_login_requerido

def panel_inicio(request):
    hoy = timezone.localdate()

    pedidos_hoy_base = Pedido.objects.filter(
        fecha_creacion__date=hoy
    ).order_by('fecha_creacion', 'idpedido')

    filtro_estado = request.GET.get('estado')
    filtro_cliente = request.GET.get('cliente', '').strip()

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
        estado = EstadoPedido.objects.filter(
            descripcion__iexact=nombre
        ).first()

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
        pedidos_hoy = pedidos_hoy.filter(
            idestadopedido_id=filtro_estado
        )

    # Cada palabra debe coincidir con el comienzo del nombre o del apellido.
    if filtro_cliente:
        for termino in filtro_cliente.split():
            pedidos_hoy = pedidos_hoy.filter(
                Q(idcliente__nombre__istartswith=termino)
                | Q(idcliente__apellido__istartswith=termino)
            )

    total_efectivo, total_transferencia = calcular_ingresos_del_dia(
        pedidos_hoy_base
    )

    respuesta = render(request, 'panel/inicioPanel.html', {
        'pedidos_hoy': pedidos_hoy,
        'estados_con_conteo': estados_con_conteo,
        'filtro_estado_actual': filtro_estado,
        'filtro_cliente_actual': filtro_cliente,
        'total_pedidos_hoy': pedidos_hoy_base.count(),
        'total_efectivo': total_efectivo,
        'total_transferencia': total_transferencia,
    })

    # El refresco automático del panel pide esta misma página por AJAX. Eso
    # no debe "gastar" los avisos (messages) pendientes: se dejan intactos
    # para que los vea la persona en su próxima carga real.
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        messages.get_messages(request).used = False

    return respuesta



@panel_login_requerido
@requiere_permiso('pedidos.ver')
def obtener_ticket_modal(request, idpedido):
    pedido = get_object_or_404(Pedido, idpedido=idpedido)

    direccion_cliente = (
        Direccion.objects.filter(idcliente=pedido.idcliente).first()
        if pedido.idcliente else None
    )

    detalles = DetallePedido.objects.filter(idpedido=pedido)

    # El subtotal de cada producto se calcula solo para mostrarlo en el ticket.
    for detalle in detalles:
        detalle.subtotal_item = detalle.preciounitario * detalle.cantidad

    # DEF-012: Obtener información amigable de la promoción para el ticket
    promocion = None
    if getattr(pedido, 'idpromocion', None):
        promocion = Promocion.objects.filter(pk=pedido.idpromocion).first()

    return render(request, 'panel/parcialTicket.html', {
        'pedido': pedido,
        'detalles': detalles,
        'direccion_cliente': direccion_cliente,
        'promocion': promocion,
    })


# Transiciones de estado permitidas (RN02). Las claves y valores se comparan
# normalizados (sin tildes, en minúsculas). "entregado" y "cancelado" son finales.
TRANSICIONES_ESTADO_PEDIDO = {
    'pendiente': {'en preparacion', 'en proceso', 'cancelado'},
    'en preparacion': {'en proceso', 'enviado', 'entregado', 'cancelado'},
    'en proceso': {'en preparacion', 'enviado', 'entregado', 'cancelado'},
    'enviado': {'entregado', 'cancelado'},
    'entregado': set(),
    'cancelado': set(),
}
MOTIVO_CANCELACION_MAX = 250


def _norm_estado(descripcion):
    return local_normalizar(descripcion or '').strip()


def _transicion_estado_valida(actual, nuevo):
    """Devuelve (ok, mensaje). `actual` y `nuevo` son EstadoPedido (actual puede ser None)."""
    if actual is None:
        return True, ''

    desde, hasta = _norm_estado(actual.descripcion), _norm_estado(nuevo.descripcion)

    if desde == hasta:
        return False, f'El pedido ya se encuentra en estado "{actual.descripcion}".'

    if desde == 'entregado':
        return False, 'Un pedido Entregado no se puede modificar ni cancelar.'

    if desde == 'cancelado':
        return False, 'Un pedido Cancelado no se puede reabrir.'

    if hasta not in TRANSICIONES_ESTADO_PEDIDO.get(desde, set()):
        return False, (
            f'No se puede pasar un pedido de "{actual.descripcion}" '
            f'a "{nuevo.descripcion}".'
        )

    return True, ''


@panel_login_requerido
@requiere_permiso('pedidos.cambiar_estado')
def actualizar_estado_pedido(request, idpedido):
    if request.method != 'POST':
        return redirect('panel_inicio')

    nuevo_estado_id = request.POST.get('nuevo_estado')

    if not nuevo_estado_id:
        return redirect('panel_inicio')

    nuevo_estado = get_object_or_404(EstadoPedido, pk=nuevo_estado_id)
    es_cancelado = _norm_estado(nuevo_estado.descripcion) == 'cancelado'
    motivo = (request.POST.get('justificacioncancelacion') or '').strip()
    estado_esperado = (request.POST.get('estado_esperado') or '').strip()

    # Validación del motivo antes de tocar la base (evita el error 500 por longitud).
    if es_cancelado:
        if not motivo:
            messages.error(request, 'Ingresá el motivo de la cancelación.')
            return redirect('panel_inicio')
        if len(motivo) > MOTIVO_CANCELACION_MAX:
            messages.error(
                request,
                f'El motivo no puede superar los {MOTIVO_CANCELACION_MAX} caracteres '
                f'(ingresaste {len(motivo)}).',
            )
            return redirect('panel_inicio')

    # Se bloquea la fila del pedido: dos cambios simultáneos se atienden en
    # secuencia y el segundo se valida contra el estado ya modificado.
    with transaction.atomic():
        pedido = get_object_or_404(
            Pedido.objects.select_for_update(), idpedido=idpedido
        )
        actual = pedido.idestadopedido

        # Otro empleado cambió el pedido mientras éste tenía el modal abierto.
        actual_id = str(actual.pk) if actual else ''
        if estado_esperado and estado_esperado != actual_id:
            messages.warning(
                request,
                f'El pedido #{pedido.idpedido} fue modificado por otro empleado '
                f'(ahora está en "{actual.descripcion if actual else "sin estado"}"). '
                'Revisá el estado actual y volvé a intentarlo.',
            )
            return redirect('panel_inicio')

        valido, mensaje_error = _transicion_estado_valida(actual, nuevo_estado)
        if not valido:
            messages.error(request, mensaje_error)
            return redirect('panel_inicio')

        pedido.idestadopedido = nuevo_estado

        if es_cancelado:
            pedido.justificacioncancelacion = motivo
            reintegrar_stock_pedido(pedido, motivo=motivo)

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


@panel_login_requerido
@requiere_permiso('pedidos.marcar_pagado')
@require_POST
def toggle_pagado(request, idpedido):
    pedido = get_object_or_404(Pedido, pk=idpedido)
    pedido.pagado = not pedido.pagado
    pedido.save()

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

@panel_login_requerido
@requiere_permiso('pedidos.ver')
def ver_ticket(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return HttpResponse(f'Visualizando el ticket del pedido #{idpedido}')


@panel_login_requerido
@requiere_permiso('pedidos.imprimir')
def imprimir_ticket(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return HttpResponse(f'Imprimiendo ticket del pedido #{idpedido}')


@panel_login_requerido
@requiere_permiso('pedidos.cambiar_estado')
def cambiar_estado_pedido(request, idpedido):
    get_object_or_404(Pedido, idpedido=idpedido)
    return redirect('panel_inicio')


# 6. PANEL - MENÚ

@panel_login_requerido
def menu_panel(request):
    return render(request, 'panel/menu/inicioMenu.html')


# Categorías

@panel_login_requerido
@requiere_permiso('categorias.ver')
def categoria_lista(request):
    return render(request, 'panel/menu/categorias/listaCategorias.html', {
        'categorias': CategoriaProducto.objects.all(),
    })


@panel_login_requerido
@requiere_permiso('categorias.crear')
def categoria_crear(request):
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            errores.append('El nombre es obligatorio.')
        elif len(nombre) > 100:
            errores.append('El nombre no puede superar los 100 caracteres.')
        elif CategoriaProducto.objects.filter(nombre__iexact=nombre).exists():
            errores.append(f'Ya existe una categoría llamada "{nombre}".')
        else:
            CategoriaProducto.objects.create(nombre=nombre)
            messages.success(request, 'Categoría creada correctamente.')
            return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/crearCategoria.html', {
        'errores': errores,
    })


@panel_login_requerido
@requiere_permiso('categorias.editar')
def categoria_editar(request, idcategoria):
    categoria = get_object_or_404(CategoriaProducto, pk=idcategoria)
    errores = []

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            errores.append('El nombre es obligatorio.')
        elif len(nombre) > 100:
            errores.append('El nombre no puede superar los 100 caracteres.')
        elif (
            CategoriaProducto.objects
            .filter(nombre__iexact=nombre)
            .exclude(pk=categoria.pk)
            .exists()
        ):
            errores.append(f'Ya existe otra categoría llamada "{nombre}".')
        else:
            categoria.nombre = nombre
            categoria.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/editarCategoria.html', {
        'categoria': categoria,
        'errores': errores,
    })


@panel_login_requerido
@requiere_permiso('categorias.eliminar')
def categoria_eliminar(request, idcategoria):
    categoria = get_object_or_404(CategoriaProducto, pk=idcategoria)

    # No se puede eliminar una categoría que todavía tiene productos
    # (incluye los ocultos o dados de baja lógica).
    cantidad_productos = Producto.objects.filter(idcategoria=categoria).count()

    if cantidad_productos:
        messages.error(
            request,
            f'No se puede eliminar la categoría "{categoria.nombre}" mientras '
            f'tenga productos asociados ({cantidad_productos}). '
            'Mové o eliminá esos productos primero.',
        )
        return redirect('categoria_lista')

    if request.method == 'POST':
        try:
            categoria.delete()
        except (IntegrityError, ProtectedError):
            messages.error(
                request,
                f'No se puede eliminar la categoría "{categoria.nombre}" '
                'porque está en uso.',
            )
            return redirect('categoria_lista')

        messages.success(request, 'Categoría eliminada.')
        return redirect('categoria_lista')

    return render(request, 'panel/menu/categorias/eliminarCategoria.html', {
        'titulo': 'categoría',
        'objeto': categoria,
        'cancel_url': 'categoria_lista',
    })


# Grupos de opciones

def _validar_grupo_opciones(min_raw, max_raw, nombres, precios, ids=None, eliminar=()):
    """
    Valida en el servidor los límites de un grupo de opciones y el precio adicional
    de cada opción. Devuelve (minimo, maximo, errores).
    - Mínimo: entero >= 0 (vacío = 0). Máximo: entero >= 1 (vacío = 1).
    - El mínimo no puede ser mayor que el máximo.
    - El precio adicional no puede ser negativo (0 sí se acepta).
    """
    errores = []

    def _entero(texto, defecto):
        texto = (texto or '').strip()
        if texto == '':
            return defecto
        try:
            return int(texto)
        except ValueError:
            return None

    minimo = _entero(min_raw, 0)
    maximo = _entero(max_raw, 1)

    if minimo is None:
        errores.append('El mínimo de selecciones debe ser un número entero.')
    elif minimo < 0:
        errores.append('El mínimo de selecciones no puede ser negativo.')

    if maximo is None:
        errores.append('El máximo de selecciones debe ser un número entero.')
    elif maximo < 1:
        errores.append('El máximo de selecciones debe ser al menos 1.')

    if not errores and minimo > maximo:
        errores.append('El mínimo de selecciones no puede ser mayor que el máximo.')

    for i, nombre in enumerate(nombres):
        if not (nombre or '').strip():
            continue
        if ids is not None and i < len(ids) and (ids[i] or '').strip() in eliminar:
            continue
        precio_raw = (precios[i] if i < len(precios) else '') or ''
        precio_raw = str(precio_raw).strip().replace(',', '.')
        if precio_raw == '':
            continue
        try:
            precio = Decimal(precio_raw)
            if not precio.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            errores.append(f'El precio adicional de "{nombre.strip()}" no es válido.')
            continue
        if precio < 0:
            errores.append(
                f'El precio adicional de "{nombre.strip()}" no puede ser negativo.'
            )

    return minimo, maximo, errores


@panel_login_requerido
@requiere_permiso('opciones.ver')
def grupo_lista(request):
    return render(request, 'panel/menu/opciones/listaOpciones.html', {
        'grupos': GrupoOpcion.objects.prefetch_related('opcion_set').all(),
    })


@panel_login_requerido
@requiere_permiso('opciones.crear')
def grupo_crear(request):
    errores = []
    insumos = Insumo.objects.all().order_by('nombreinsumo')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        opcion_nombres = request.POST.getlist('opcion_nombre[]')
        opcion_precios = request.POST.getlist('opcion_precio[]')
        opcion_insumos = request.POST.getlist('opcion_insumo[]')
        opcion_cantidades = request.POST.getlist('opcion_cantidad_insumo[]')

        minselecciones, maxselecciones, errores_grupo = _validar_grupo_opciones(
            request.POST.get('minselecciones'),
            request.POST.get('maxselecciones'),
            opcion_nombres,
            opcion_precios,
        )

        if not nombre:
            errores.append('El nombre del grupo es obligatorio.')
        errores.extend(errores_grupo)

        if not errores:
            grupo = GrupoOpcion.objects.create(
                nombre=nombre,
                minselecciones=minselecciones,
                maxselecciones=maxselecciones,
            )

            total_opc = len(opcion_nombres)
            for i in range(total_opc):
                nom = opcion_nombres[i].strip() if i < len(opcion_nombres) else ''
                if not nom:
                    continue
                precio = opcion_precios[i] if i < len(opcion_precios) else 0
                insumo_id = opcion_insumos[i] if i < len(opcion_insumos) else None
                cant_ins = opcion_cantidades[i] if i < len(opcion_cantidades) else 1

                insumo_obj = Insumo.objects.filter(pk=insumo_id).first() if insumo_id and str(insumo_id).isdigit() else None
                try:
                    cant_dec = Decimal(str(cant_ins)) if cant_ins else Decimal('1.00')
                    if cant_dec <= 0:
                        cant_dec = Decimal('1.00')
                except Exception:
                    cant_dec = Decimal('1.00')

                Opcion.objects.create(
                    idgrupo=grupo,
                    nombre=nom,
                    precioadicional=precio or 0,
                    idinsumo=insumo_obj,
                    cantidad_insumo=cant_dec,
                )

            messages.success(
                request, 'Grupo de opciones creado correctamente.'
            )
            return redirect('grupo_lista')

    return render(request, 'panel/menu/opciones/crearGrupo.html', {
        'errores': errores,
        'insumos': insumos,
    })


@panel_login_requerido
@requiere_permiso('opciones.editar')
def grupo_editar(request, idgrupo):
    grupo = get_object_or_404(GrupoOpcion, pk=idgrupo)
    errores = []
    insumos = Insumo.objects.all().order_by('nombreinsumo')

    print(request.POST)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        minselecciones, maxselecciones, errores_grupo = _validar_grupo_opciones(
            request.POST.get('minselecciones'),
            request.POST.get('maxselecciones'),
            request.POST.getlist('opcion_nombre[]'),
            request.POST.getlist('opcion_precio[]'),
            ids=request.POST.getlist('opcion_id[]'),
            eliminar=set(request.POST.getlist('opcion_eliminar[]')),
        )

        if not nombre:
            errores.append('El nombre del grupo es obligatorio.')
        errores.extend(errores_grupo)

        if not errores:
            grupo.minselecciones = minselecciones
            grupo.maxselecciones = maxselecciones
            grupo.nombre = nombre
            grupo.save()

            opcion_ids = request.POST.getlist('opcion_id[]')
            opcion_nombres = request.POST.getlist('opcion_nombre[]')
            opcion_precios = request.POST.getlist('opcion_precio[]')
            opcion_insumos = request.POST.getlist('opcion_insumo[]')
            opcion_cantidades = request.POST.getlist('opcion_cantidad_insumo[]')
            opcion_eliminar = set(request.POST.getlist('opcion_eliminar[]'))

            no_eliminadas = []
            for opc_eliminar in Opcion.objects.filter(idgrupo=grupo, pk__in=opcion_eliminar):
                # Una por una: si una está vinculada a otros registros no
                # bloquea la eliminación de las demás.
                try:
                    with transaction.atomic():
                        opc_eliminar.delete()
                except (ProtectedError, IntegrityError):
                    no_eliminadas.append(opc_eliminar.nombre)

            if no_eliminadas:
                messages.warning(
                    request,
                    'No se pudieron eliminar estas opciones porque están vinculadas '
                    'a otros registros: ' + ', '.join(no_eliminadas) + '.'
                )

            total_opc = len(opcion_nombres)
            for i in range(total_opc):
                opc_id_raw = opcion_ids[i].strip() if i < len(opcion_ids) else ''
                if opc_id_raw in opcion_eliminar:
                    continue

                nom = opcion_nombres[i].strip() if i < len(opcion_nombres) else ''
                if not nom:
                    continue

                precio = opcion_precios[i] if i < len(opcion_precios) else 0
                insumo_id = opcion_insumos[i] if i < len(opcion_insumos) else None
                cant_ins = opcion_cantidades[i] if i < len(opcion_cantidades) else 1

                insumo_obj = Insumo.objects.filter(pk=insumo_id).first() if insumo_id and str(insumo_id).isdigit() else None
                try:
                    cant_dec = Decimal(str(cant_ins)) if cant_ins else Decimal('1.00')
                    if cant_dec <= 0:
                        cant_dec = Decimal('1.00')
                except Exception:
                    cant_dec = Decimal('1.00')

                if opc_id_raw and opc_id_raw.isdigit():
                    opcion_obj = Opcion.objects.filter(pk=int(opc_id_raw), idgrupo=grupo).first()
                    if opcion_obj:
                        opcion_obj.nombre = nom
                        opcion_obj.precioadicional = precio or 0
                        opcion_obj.idinsumo = insumo_obj
                        opcion_obj.cantidad_insumo = cant_dec
                        opcion_obj.save()
                else:
                    Opcion.objects.create(
                        idgrupo=grupo,
                        nombre=nom,
                        precioadicional=precio or 0,
                        idinsumo=insumo_obj,
                        cantidad_insumo=cant_dec,
                    )

            if not no_eliminadas:
                messages.success(request, 'Grupo actualizado correctamente.')
            return redirect('grupo_lista')

    return render(request, 'panel/menu/opciones/editarGrupo.html', {
        'grupo': grupo,
        'opciones': grupo.opcion_set.select_related('idinsumo').all(),
        'insumos': insumos,
        'errores': errores,
    })


@panel_login_requerido
@requiere_permiso('opciones.eliminar')
def grupo_eliminar(request, idgrupo):
    grupo = get_object_or_404(GrupoOpcion, pk=idgrupo)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Desvincular de productos antes de eliminar para no violar integridad referencial
                ProductoGrupoOpcion.objects.filter(idgrupo=grupo).delete()

                grupo.opcion_set.all().delete()

                # Eliminar el grupo cuando ya no tenga opciones.
                grupo.delete()

            messages.success(
                request,
                'Grupo y opciones eliminados correctamente.'
            )
            return redirect('grupo_lista')

        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                'No se puede eliminar este grupo porque sus opciones '
                'están relacionadas con otros registros. '
                'Primero debes quitar o modificar esas relaciones.'
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


# Productos

def _ids_enviados(request, campo):
    return [int(v) for v in request.POST.getlist(campo) if v.isdigit()]


DESCRIPCION_PRODUCTO_MAX = 1000
PRECIO_PRODUCTO_MAX = Decimal('99999999.99')


def _largo_texto_visible(texto):
    """Largo del texto sin etiquetas HTML (la descripción viene de CKEditor)."""
    import html as html_lib
    from django.utils.html import strip_tags

    plano = html_lib.unescape(strip_tags(texto or ''))
    return len(plano.replace('\xa0', ' ').strip())


def _validar_producto(nombre, precio_raw, idcategoria=None, descripcion=''):
    """Devuelve (precio, errores) para los datos básicos del producto."""
    errores = []

    if not nombre:
        errores.append('El nombre del producto es obligatorio.')
    elif len(nombre) > 100:
        errores.append('El nombre no puede superar los 100 caracteres.')

    precio = None

    try:
        precio = Decimal(precio_raw)

        if not precio.is_finite():
            raise InvalidOperation

        if precio <= Decimal('0.00'):
            errores.append('El precio debe ser mayor a 0 (mínimo 0,01).')
        elif precio.as_tuple().exponent < -2:
            errores.append('El precio admite como máximo 2 decimales.')
        elif precio > PRECIO_PRODUCTO_MAX:
            errores.append('El precio ingresado es demasiado alto.')

    except (InvalidOperation, ValueError, TypeError):
        precio = None
        errores.append('El precio debe ser un número válido.')

    if not idcategoria or not CategoriaProducto.objects.filter(
        pk=idcategoria
    ).exists():
        errores.append('Seleccioná una categoría para el producto.')

    largo = _largo_texto_visible(descripcion)
    if largo > DESCRIPCION_PRODUCTO_MAX:
        errores.append(
            f'La descripción no puede superar los {DESCRIPCION_PRODUCTO_MAX} '
            f'caracteres (tiene {largo}).'
        )

    return precio, errores


def _guardar_relaciones_producto(producto, grupos_ids, extras_ids):
    """Reemplaza los grupos de opciones y extras del producto."""
    ProductoGrupoOpcion.objects.filter(idproducto=producto).delete()

    for grupo in GrupoOpcion.objects.filter(pk__in=grupos_ids):
        ProductoGrupoOpcion.objects.create(idproducto=producto, idgrupo=grupo)

    ProductoExtras.objects.filter(idproducto=producto).delete()

    for extra in Extras.objects.filter(pk__in=extras_ids):
        ProductoExtras.objects.create(idproducto=producto, idextra=extra)


@panel_login_requerido
@requiere_permiso('productos.ver')
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


@panel_login_requerido
@requiere_permiso('productos.crear')
def producto_crear(request):
    contexto = {
        'categorias': CategoriaProducto.objects.all(),
        'grupos': GrupoOpcion.objects.prefetch_related('opcion_set').all(),
        'extras': Extras.objects.all(),
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

    precio, errores = _validar_producto(
        nombre, precio_raw, idcategoria, request.POST.get('descripcion', '')
    )

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


@panel_login_requerido
@requiere_permiso('productos.editar')
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

    precio, errores = _validar_producto(
        nombre, precio_raw, idcategoria, descripcion
    )

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


@panel_login_requerido
@requiere_algun_permiso(['productos.editar', 'productos.eliminar'])
def producto_ocultar(request, idproducto):
    """
    Oculta el producto del menú público (o lo vuelve a mostrar). No se borra nada:
    siguen existiendo su receta, sus extras y el historial de pedidos.
    """
    producto = get_object_or_404(Producto, pk=idproducto)
    esta_oculto = producto.idestadoproducto_id in ESTADOS_NO_VISIBLES

    if request.method == 'POST':
        nuevo_estado = ESTADO_ACTIVO if esta_oculto else ESTADO_OCULTO

        # update() evita ejecutar el save() del modelo (conversión de imagen).
        Producto.objects.filter(pk=producto.pk).update(
            idestadoproducto=nuevo_estado
        )

        messages.success(
            request,
            f'Producto "{producto.nombre}" '
            f'{"visible nuevamente en el menú" if esta_oculto else "oculto del menú"}.'
        )
        return redirect('producto_lista')

    return render(request, 'panel/menu/productos/eliminarProducto.html', {
        'producto': producto,
        'modo': 'mostrar' if esta_oculto else 'ocultar',
        'cancel_url': 'producto_lista',
    })


@panel_login_requerido
@requiere_permiso('productos.eliminar')
def producto_eliminar_definitivo(request, idproducto):
    """
    Borra el producto de verdad de la base de datos.

    Para no romper el historial: los detalles de pedidos viejos conservan el nombre
    (DetallePedido.nombreproducto) y pasan a no tener producto asociado; la receta, los
    extras, los grupos de opciones y las promociones del producto se eliminan con él.
    """
    producto = get_object_or_404(Producto, pk=idproducto)

    cant_pedidos = (
        DetallePedido.objects.filter(idproducto=producto)
        .values('idpedido').distinct().count()
    )
    cant_promociones = ProductoPromocion.objects.filter(idproducto=producto).count()

    contexto = {
        'producto': producto,
        'modo': 'eliminar',
        'cant_pedidos': cant_pedidos,
        'cant_promociones': cant_promociones,
        'cancel_url': 'producto_lista',
    }

    if request.method != 'POST':
        return render(request, 'panel/menu/productos/eliminarProducto.html', contexto)

    confirmacion = (request.POST.get('confirmacion') or '').strip().lower()
    if confirmacion != (producto.nombre or '').strip().lower():
        messages.error(
            request,
            'Para borrar definitivamente tenés que escribir el nombre exacto del producto.'
        )
        return render(request, 'panel/menu/productos/eliminarProducto.html', contexto)

    nombre = producto.nombre
    imagen_storage = producto.imagen.storage if producto.imagen else None
    imagen_nombre = producto.imagen.name if producto.imagen else None

    with transaction.atomic():
        # 1. El historial conserva el nombre y deja de apuntar al producto.
        DetallePedido.objects.filter(
            idproducto=producto, nombreproducto__isnull=True
        ).update(nombreproducto=(nombre or '')[:100])
        DetallePedido.objects.filter(idproducto=producto).update(idproducto=None)

        # 2. Todo lo que depende del producto.
        RecetaInsumo.objects.filter(idreceta__idproducto=producto).delete()
        Receta.objects.filter(idproducto=producto).delete()
        ProductoExtras.objects.filter(idproducto=producto).delete()
        ProductoGrupoOpcion.objects.filter(idproducto=producto).delete()
        ProductoPromocion.objects.filter(idproducto=producto).delete()

        # 3. El producto.
        producto.delete()

    # La imagen se borra después de confirmar la transacción (si falla no importa).
    if imagen_storage and imagen_nombre:
        try:
            imagen_storage.delete(imagen_nombre)
        except Exception:
            logger.warning('No se pudo borrar la imagen "%s".', imagen_nombre)

    registrar_auditoria(
        request,
        'PRODUCTO_ELIMINAR',
        f'Producto "{nombre}" eliminado definitivamente '
        f'({cant_pedidos} pedidos históricos conservados).',
    )
    messages.success(
        request,
        f'Producto "{nombre}" eliminado definitivamente. '
        f'Los {cant_pedidos} pedidos que lo incluían siguen en el historial.'
    )
    return redirect('producto_lista')


# Extras

@panel_login_requerido
@requiere_permiso('extras.ver')
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


@panel_login_requerido
@requiere_permiso('extras.crear')
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


@panel_login_requerido
@requiere_permiso('extras.editar')
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


@panel_login_requerido
@requiere_permiso('extras.eliminar')
def extra_eliminar(request, idextra):
    extra = get_object_or_404(Extras, pk=idextra)
    cant_productos = ProductoExtras.objects.filter(idextra=extra).count()

    if request.method == 'POST':
        nombre_extra = extra.nombre

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


# Recetas

@panel_login_requerido
@requiere_permiso('recetas.administrar')
def gestionar_receta(request, idproducto):
    producto = get_object_or_404(Producto, pk=idproducto)
    receta, _ = Receta.objects.get_or_create(idproducto=producto)

    origen = request.GET.get('origen') or request.POST.get('origen', '')

    if request.method == 'POST':
        id_insumo = request.POST.get('id_insumo')
        cantidad_texto = request.POST.get('cantidadinsumo', '').strip()
        es_removible = request.POST.get('es_removible') == 'on'

        if not id_insumo:
            messages.error(request, 'Tenés que seleccionar un insumo.')

        else:
            try:
                cantidad = Decimal(cantidad_texto)

                if (
                    not cantidad.is_finite()
                    or cantidad <= 0
                    or cantidad.as_tuple().exponent < -2
                ):
                    raise InvalidOperation

            except (InvalidOperation, ValueError):
                messages.error(
                    request,
                    'Ingresá una cantidad mayor que cero, '
                    'con hasta dos decimales.'
                )

            else:
                insumo = get_object_or_404(Insumo, pk=id_insumo)

                existe = RecetaInsumo.objects.filter(
                    idreceta=receta,
                    idinsumo=insumo,
                ).exists()

                if existe:
                    messages.warning(
                        request,
                        f'El insumo "{insumo.nombreinsumo}" '
                        'ya está en esta receta.'
                    )

                else:
                    try:
                        with transaction.atomic():
                            RecetaInsumo.objects.create(
                                idreceta=receta,
                                idinsumo=insumo,
                                cantidadinsumo=cantidad,
                                unidadmedida=insumo.unidadmedidaegreso,
                                es_removible=es_removible,
                            )

                        messages.success(
                            request,
                            f'"{insumo.nombreinsumo}" '
                            'se agregó correctamente a la receta.'
                        )

                    except IntegrityError:
                        messages.error(
                            request,
                            'No se pudo guardar el ingrediente. '
                            'Verificá que la tabla RecetaInsumo '
                            'tenga las columnas correctas en SQL Server.'
                        )

        url = reverse(
            'gestionar_receta',
            kwargs={'idproducto': producto.idproducto},
        )

        if origen:
            url += f'?origen={quote(origen)}'

        return redirect(url)

    detalles_receta = (
        RecetaInsumo.objects
        .filter(idreceta=receta)
        .select_related('idinsumo')
    )

    return render(request, 'panel/menu/productos/gestionarReceta.html', {
        'producto': producto,
        'receta': receta,
        'detalles_receta': detalles_receta,
        'todos_los_insumos': Insumo.objects.all(),
        'origen': origen,
    })


@panel_login_requerido
@requiere_permiso('recetas.administrar')
def eliminar_insumo_receta(request, idrecetainsumo):
    detalle = get_object_or_404(RecetaInsumo, pk=idrecetainsumo)

    id_producto = detalle.idreceta.idproducto.idproducto
    origen = request.GET.get('origen', '')

    nombre_insumo = (
        detalle.idinsumo.nombreinsumo if detalle.idinsumo else 'Insumo'
    )

    if request.method == 'POST':
        detalle.delete()
        messages.success(
            request,
            f'Insumo "{nombre_insumo}" quitado de la receta.'
        )
    else:
        messages.warning(
            request,
            'Para quitar un ingrediente, se necesita una solicitud POST.'
        )

    url = reverse('gestionar_receta', kwargs={'idproducto': id_producto})

    if origen:
        url += f'?origen={quote(origen)}'

    return redirect(url)


@panel_login_requerido
@requiere_permiso('recetas.administrar')
def editar_cantidad_insumo_receta(request, idrecetainsumo):
    detalle = get_object_or_404(
        RecetaInsumo.objects.select_related(
            'idreceta',
            'idreceta__idproducto',
            'idinsumo',
        ),
        pk=idrecetainsumo,
    )

    producto = detalle.idreceta.idproducto

    origen = request.POST.get('origen', '') or request.GET.get('origen', '')

    if request.method != 'POST':
        return redirect('gestionar_receta', idproducto=producto.idproducto)

    cantidad_texto = request.POST.get('cantidadinsumo', '').strip()

    try:
        cantidad = Decimal(cantidad_texto)

        if (
            not cantidad.is_finite()
            or cantidad <= 0
            or cantidad.as_tuple().exponent < -2
        ):
            raise InvalidOperation

    except (InvalidOperation, ValueError):
        messages.error(
            request,
            'Ingresá una cantidad mayor que cero, con hasta dos decimales.'
        )

    else:
        detalle.cantidadinsumo = cantidad
        update_fields = ['cantidadinsumo']

        # La cantidad se carga en la unidad de egreso del insumo: se deja
        # guardada para que el descuento de stock convierta bien (g -> kg).
        if detalle.idinsumo and detalle.unidadmedida != detalle.idinsumo.unidadmedidaegreso:
            detalle.unidadmedida = detalle.idinsumo.unidadmedidaegreso
            update_fields.append('unidadmedida')

        detalle.save(update_fields=update_fields)

        nombre_insumo = (
            detalle.idinsumo.nombreinsumo if detalle.idinsumo
            else 'Ingrediente'
        )

        messages.success(
            request,
            f'La cantidad de "{nombre_insumo}" se actualizó correctamente.'
        )

    url = reverse(
        'gestionar_receta',
        kwargs={'idproducto': producto.idproducto},
    )

    if origen:
        url += f'?origen={quote(origen)}'

    return redirect(url)


# 7. PANEL - PROMOCIONES

TEMPLATE_FORM_PROMOCION = 'panel/promociones/formPromocion.html'


def _valor_beneficio(tipo_beneficio, valor_raw):
    """Los beneficios sin valor numérico (ej. 2x1) se guardan como NULL."""
    if tipo_beneficio.comportamiento == 'SIN_VALOR' or not valor_raw:
        return None

    return valor_raw


def _form_promocion_con_error(request, contexto, mensaje):
    # Se devuelve lo que la persona había escrito para no perder los datos.
    return render(request, TEMPLATE_FORM_PROMOCION, {
        **contexto,
        'error': mensaje,
        'datos': request.POST,
    })


@panel_login_requerido
@requiere_permiso('promociones.ver')
def promociones_panel(request):
    return render(request, 'panel/promociones/inicioPromociones.html')


@panel_login_requerido
@requiere_permiso('promociones.ver')
def lista_promociones(request):
    return render(request, 'panel/promociones/listaPromociones.html', {
        'promociones': Promocion.objects.all(),
    })


@panel_login_requerido
@requiere_permiso('promociones.crear')
def crear_promocion(request):
    contexto = {
        'titulo': 'Crear promoción',
        'tipos_beneficio': TipoBeneficio.objects.all(),
        'productos': Producto.objects.all(),
    }

    if request.method != 'POST':
        return render(request, TEMPLATE_FORM_PROMOCION, contexto)

    palabraclave = request.POST.get('palabraclave', '').strip()
    tipobeneficio_id = request.POST.get('tipobeneficio')
    producto_id = request.POST.get('producto')
    descuento = request.POST.get('descuento', '').strip()
    fechainicio = request.POST.get('fechainicio') or None
    fechafin = request.POST.get('fechafin') or None
    activo = 1 if request.POST.get('activo') else 0

    if not palabraclave:
        return _form_promocion_con_error(
            request, contexto, 'Ingresá una palabra clave.'
        )

    if not tipobeneficio_id:
        return _form_promocion_con_error(
            request, contexto, 'Seleccioná un tipo de beneficio.'
        )

    if not producto_id:
        return _form_promocion_con_error(
            request, contexto, 'Seleccioná un producto.'
        )

    if Promocion.objects.filter(palabraclave__iexact=palabraclave).exists():
        return _form_promocion_con_error(
            request, contexto, f'Ya existe una promoción registrada con la palabra clave "{palabraclave}".'
        )

    # Validar que fecha de finalización no sea menor a la de inicio
    if fechainicio and fechafin and fechafin < fechainicio:
        return _form_promocion_con_error(
            request, contexto, 'La fecha de finalización no puede ser menor a la fecha de inicio.'
        )

    try:
        tipo_beneficio = TipoBeneficio.objects.get(pk=tipobeneficio_id)
    except TipoBeneficio.DoesNotExist:
        return _form_promocion_con_error(
            request, contexto, 'El tipo de beneficio seleccionado no existe.'
        )

    try:
        producto = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        return _form_promocion_con_error(
            request, contexto, 'El producto seleccionado no existe.'
        )

    valor = None

    if getattr(tipo_beneficio, 'comportamiento', None) != 'SIN_VALOR':
        if not descuento:
            return _form_promocion_con_error(
                request, contexto, 'Ingresá el valor del beneficio.'
            )

        try:
            valor = Decimal(descuento)
        except (InvalidOperation, TypeError):
            return _form_promocion_con_error(
                request, contexto, 'El valor del beneficio no es válido.'
            )

        if valor < 0:
            return _form_promocion_con_error(
                request, contexto,
                'El valor del beneficio no puede ser negativo.'
            )

        if (
            getattr(tipo_beneficio, 'comportamiento', None) == 'PORCENTAJE'
            and not (Decimal('0') < valor <= Decimal('100'))
        ):
            return _form_promocion_con_error(
                request, contexto,
                'El porcentaje debe ser mayor a 0 y no puede superar 100.'
            )

    promocion = Promocion(
        palabraclave=palabraclave,
        tipobeneficio=tipo_beneficio,
        valor=valor,
        fechainicio=fechainicio,
        fechafin=fechafin,
        activo=activo,
    )
    promocion.save()

    ProductoPromocion.objects.create(
        idproducto=producto,
        idpromocion=promocion,
    )

    messages.success(
        request,
        f'La promoción "{palabraclave}" fue creada correctamente.'
    )
    return redirect('panel_lista_promociones')


@panel_login_requerido
@requiere_permiso('promociones.editar')
def editar_promocion(request, idpromocion):
    promocion = get_object_or_404(Promocion, idpromocion=idpromocion)

    relacion_producto = (
        ProductoPromocion.objects
        .filter(idpromocion=promocion)
        .select_related('idproducto')
        .first()
    )

    contexto = {
        'titulo': 'Editar promoción',
        'promocion': promocion,
        'tipos_beneficio': TipoBeneficio.objects.all(),
        'productos': Producto.objects.all(),
        'tipo_beneficio_seleccionado': (
            promocion.tipobeneficio.pk if promocion.tipobeneficio else None
        ),
        'producto_seleccionado': (
            relacion_producto.idproducto.pk
            if relacion_producto and relacion_producto.idproducto
            else None
        ),
    }

    if request.method != 'POST':
        return render(request, TEMPLATE_FORM_PROMOCION, contexto)

    palabraclave = request.POST.get('palabraclave', '').strip()
    tipobeneficio_id = request.POST.get('tipobeneficio')
    producto_id = request.POST.get('producto')
    descuento = request.POST.get('descuento', '').strip()
    fechainicio = request.POST.get('fechainicio') or None
    fechafin = request.POST.get('fechafin') or None
    activo = 1 if request.POST.get('activo') else 0

    if not palabraclave:
        return _form_promocion_con_error(
            request, contexto, 'Ingresá una palabra clave.'
        )

    if not tipobeneficio_id:
        return _form_promocion_con_error(
            request, contexto, 'Seleccioná un tipo de beneficio.'
        )

    if not producto_id:
        return _form_promocion_con_error(
            request, contexto, 'Seleccioná un producto.'
        )

    if Promocion.objects.filter(palabraclave__iexact=palabraclave).exclude(pk=promocion.pk).exists():
        return _form_promocion_con_error(
            request, contexto, f'Ya existe otra promoción registrada con la palabra clave "{palabraclave}".'
        )

    # Validar que fecha de finalización no sea menor a la de inicio
    if fechainicio and fechafin and fechafin < fechainicio:
        return _form_promocion_con_error(
            request, contexto, 'La fecha de finalización no puede ser menor a la fecha de inicio.'
        )

    try:
        tipo_beneficio = TipoBeneficio.objects.get(pk=tipobeneficio_id)
    except TipoBeneficio.DoesNotExist:
        return _form_promocion_con_error(
            request, contexto, 'El tipo de beneficio seleccionado no existe.'
        )

    try:
        producto = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        return _form_promocion_con_error(
            request, contexto, 'El producto seleccionado no existe.'
        )

    valor = None

    if getattr(tipo_beneficio, 'comportamiento', None) != 'SIN_VALOR':
        if not descuento:
            return _form_promocion_con_error(
                request, contexto, 'Ingresá el valor del beneficio.'
            )

        try:
            valor = Decimal(descuento)
        except (InvalidOperation, TypeError):
            return _form_promocion_con_error(
                request, contexto, 'El valor del beneficio no es válido.'
            )

        if valor < 0:
            return _form_promocion_con_error(
                request, contexto,
                'El valor del beneficio no puede ser negativo.'
            )

        if (
            getattr(tipo_beneficio, 'comportamiento', None) == 'PORCENTAJE'
            and not (Decimal('0') < valor <= Decimal('100'))
        ):
            return _form_promocion_con_error(
                request, contexto,
                'El porcentaje debe ser mayor a 0 y no puede superar 100.'
            )

    promocion.palabraclave = palabraclave
    promocion.tipobeneficio = tipo_beneficio
    promocion.valor = valor
    promocion.fechainicio = fechainicio
    promocion.fechafin = fechafin
    promocion.activo = activo
    promocion.save()

    ProductoPromocion.objects.filter(idpromocion=promocion).delete()
    ProductoPromocion.objects.create(
        idproducto=producto,
        idpromocion=promocion,
    )

    messages.success(
        request,
        f'La promoción "{palabraclave}" fue actualizada correctamente.'
    )
    return redirect('panel_lista_promociones')


@panel_login_requerido
@requiere_permiso('promociones.eliminar')
def eliminar_promocion(request, idpromocion):
    promocion = get_object_or_404(Promocion, pk=idpromocion)

    if request.method == 'POST':
        nombre_promo = promocion.palabraclave or f"#{promocion.pk}"
        with transaction.atomic():
            ProductoPromocion.objects.filter(idpromocion=promocion).delete()
            promocion.delete()

        # DEF-015: Redirección limpia y mensaje de éxito
        messages.success(request, f'La promoción "{nombre_promo}" fue eliminada correctamente.')
        return redirect('panel_lista_promociones')

    return render(request, 'panel/promociones/EliminarPromocion.html', {
        'promocion': promocion,
    })


# Tipos de beneficio

@panel_login_requerido
@requiere_permiso('tipos_beneficio.administrar')
def lista_tipos_beneficio(request):
    return render(
        request,
        'panel/promociones/tiposBeneficio/listaTiposBeneficios.html',
        {'tipos': TipoBeneficio.objects.all()},
    )


TEMPLATE_CREAR_TIPO_BENEFICIO = (
    'panel/promociones/tiposBeneficio/crearTipoBeneficio.html'
)
TEMPLATE_EDITAR_TIPO_BENEFICIO = (
    'panel/promociones/tiposBeneficio/editarTipoBeneficio.html'
)


def _codigo_desde_nombre(nombre):
    """Código de un tipo de beneficio: siempre se deriva del nombre.

    'Descuento 20%' -> 'DESCUENTO_20', 'Producto gratis' -> 'PRODUCTO_GRATIS'.
    Debe coincidir con generarCodigo() de los templates crear/editarTipoBeneficio.
    """
    texto = unicodedata.normalize('NFD', nombre or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[^A-Z0-9]+', '_', texto.upper())
    return texto.strip('_')[:50].rstrip('_')


def _tipo_beneficio_con_error(request, template, mensaje, tipo=None):
    """Vuelve a mostrar el formulario con el error y lo que se había escrito."""
    contexto = {'errores': [mensaje], 'datos': request.POST}

    if tipo is not None:
        contexto['tipo'] = tipo

    return render(request, template, contexto)


@panel_login_requerido
@requiere_permiso('tipos_beneficio.administrar')
def crear_tipo_beneficio(request):
    if request.method == 'GET':
        return render(request, TEMPLATE_CREAR_TIPO_BENEFICIO)

    nombre = request.POST.get('nombre', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    comportamiento = request.POST.get('comportamiento', '').strip()

    def error(mensaje):
        return _tipo_beneficio_con_error(
            request, TEMPLATE_CREAR_TIPO_BENEFICIO, mensaje
        )

    if not nombre:
        return error('Debes ingresar un nombre para el beneficio.')

    if comportamiento not in dict(TipoBeneficio.OPCIONES_COMPORTAMIENTO):
        return error('Debes seleccionar un comportamiento.')

    # El código siempre se genera a partir del nombre (se ignora lo que llegue del formulario).
    codigo = _codigo_desde_nombre(nombre)

    if not codigo:
        return error('El nombre debe incluir al menos una letra o un número.')

    if TipoBeneficio.objects.filter(codigo__iexact=codigo).exists():
        return error('Ya existe un tipo de beneficio con un nombre equivalente (mismo código).')

    if TipoBeneficio.objects.filter(nombre__iexact=nombre).exists():
        return error('Ya existe un tipo de beneficio con ese nombre.')

    TipoBeneficio.objects.create(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        comportamiento=comportamiento,
    )

    messages.success(request, 'Tipo de beneficio creado correctamente.')
    return redirect('panel_lista_tipos_beneficio')


@panel_login_requerido
@requiere_permiso('tipos_beneficio.administrar')
def editar_tipo_beneficio(request, pk):
    tipo = get_object_or_404(TipoBeneficio, pk=pk)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        comportamiento = request.POST.get('comportamiento', '').strip()

        def error(mensaje):
            return _tipo_beneficio_con_error(
                request, TEMPLATE_EDITAR_TIPO_BENEFICIO, mensaje, tipo
            )

        if not nombre:
            return error('El nombre no puede estar vacío.')

        if comportamiento not in dict(TipoBeneficio.OPCIONES_COMPORTAMIENTO):
            return error('Debes seleccionar un comportamiento.')

        # El código siempre se regenera a partir del nombre (se ignora lo que llegue del formulario).
        codigo = _codigo_desde_nombre(nombre)

        if not codigo:
            return error('El nombre debe incluir al menos una letra o un número.')

        # Evitar códigos duplicados en otros registros.
        if (
            TipoBeneficio.objects
            .filter(codigo__iexact=codigo)
            .exclude(pk=pk)
            .exists()
        ):
            return error('Ya existe otro beneficio con un nombre equivalente (mismo código).')

        # Evitar nombres duplicados en otros registros.
        if (
            TipoBeneficio.objects
            .filter(nombre__iexact=nombre)
            .exclude(pk=pk)
            .exists()
        ):
            return error('Ya existe otro beneficio con ese nombre.')

        tipo.codigo = codigo
        tipo.nombre = nombre
        tipo.descripcion = descripcion
        tipo.comportamiento = comportamiento
        tipo.save()

        messages.success(
            request,
            'Tipo de beneficio modificado correctamente.'
        )
        return redirect('panel_lista_tipos_beneficio')

    return render(request, TEMPLATE_EDITAR_TIPO_BENEFICIO, {'tipo': tipo})


@panel_login_requerido
@requiere_permiso('tipos_beneficio.administrar')
def eliminar_tipo_beneficio(request, pk):
    tipo = get_object_or_404(TipoBeneficio, pk=pk)

    if request.method == 'GET':
        return render(
            request,
            'panel/promociones/tiposBeneficio/eliminarTipoBeneficio.html',
            {'tipo': tipo},
        )

    if Promocion.objects.filter(tipobeneficio=tipo).exists():
        messages.error(
            request,
            'No puedes eliminar este beneficio porque tiene '
            'promociones asociadas.'
        )
        return redirect('panel_lista_tipos_beneficio')

    tipo.delete()

    messages.success(request, 'Tipo de beneficio eliminado correctamente.')
    return redirect('panel_lista_tipos_beneficio')


# 8. PANEL - STOCK


@panel_login_requerido
@requiere_permiso('stock.ver')
def stock_lista(request):
    hoy = timezone.localdate()
    fecha_limite = hoy + timedelta(days=7)

    insumos = Insumo.objects.all().order_by('nombreinsumo')

    # Insumos con stock en el mínimo o por debajo.
    insumos_criticos = [
        insumo
        for insumo in insumos
        if insumo.stockactual <= insumo.stockminimo
    ]

    # Lotes que vencen hoy o durante los próximos 7 días.
    lotes_por_vencer = (
        Lote.objects
        .filter(
            fechavencimiento__gte=hoy,
            fechavencimiento__lte=fecha_limite,
            cantidadactual__gt=0,
        )
        .select_related('idinsumo')
        .order_by(
            'fechavencimiento',
            'idinsumo__nombreinsumo',
        )
    )

    # Lotes vencidos que todavía tienen cantidad registrada.
    lotes_vencidos = (
        Lote.objects
        .filter(
            fechavencimiento__lt=hoy,
            cantidadactual__gt=0,
        )
        .select_related('idinsumo')
        .order_by(
            'fechavencimiento',
            'idinsumo__nombreinsumo',
        )
    )

    # Listado completo de lotes.
    lotes = (
        Lote.objects
        .select_related('idinsumo')
        .order_by('-fechaingreso', '-idlote')
    )

    # Historial de compras y sus detalles.
    compras = (
        Compras.objects
        .prefetch_related('detallecompra_set__idinsumo')
        .order_by('-fecha', '-idcompra')
    )

    contexto = {
        'insumos': insumos,
        'insumos_criticos': insumos_criticos,
        'lotes': lotes,
        'compras': compras,
        'lotes_por_vencer': lotes_por_vencer,
        'lotes_vencidos': lotes_vencidos,
        'insumos_sin_conversion': [i for i in insumos if not i.conversion_valida],
        'hoy': hoy,
        'fecha_limite': fecha_limite,
    }

    return render(
        request,
        'panel/stock/stockLista.html',
        contexto,
    )


@panel_login_requerido
@requiere_permiso('stock.ver')
def imprimir_lote_codigo(request, idlote):
    """
    Vista de impresión de etiqueta individual de un lote con su código de barras Code 128.
    """
    lote = get_object_or_404(
        Lote.objects.select_related('idinsumo'),
        pk=idlote
    )
    hoy = timezone.localdate()
    fecha_limite = hoy + timedelta(days=7)

    esta_vencido = bool(lote.fechavencimiento and lote.fechavencimiento < hoy)
    vence_pronto = bool(lote.fechavencimiento and hoy <= lote.fechavencimiento <= fecha_limite)

    codigo_para_barras = lote.codigo or f"LOT-{lote.pk:03d}"
    barcode_svg = generar_codigo_barras_svg(codigo_para_barras)

    item = {
        'lote': lote,
        'barcode_svg': barcode_svg,
        'esta_vencido': esta_vencido,
        'vence_pronto': vence_pronto,
    }

    return render(
        request,
        'panel/stock/etiquetaLote.html',
        {
            'lote': lote,
            'lotes_con_svg': [item],
            'es_lote_individual': True,
            'autoprint': request.GET.get('autoprint') == '1',
        }
    )


@panel_login_requerido
@requiere_permiso('stock.ver')
def imprimir_lotes_codigos(request):
    """
    Vista para imprimir todas las etiquetas de lotes registrados en lote.
    """
    lotes = (
        Lote.objects
        .select_related('idinsumo')
        .order_by('-fechaingreso', '-idlote')
    )

    hoy = timezone.localdate()
    fecha_limite = hoy + timedelta(days=7)

    lotes_con_svg = []
    for lote in lotes:
        esta_vencido = bool(lote.fechavencimiento and lote.fechavencimiento < hoy)
        vence_pronto = bool(lote.fechavencimiento and hoy <= lote.fechavencimiento <= fecha_limite)
        codigo_para_barras = lote.codigo or f"LOT-{lote.pk:03d}"
        barcode_svg = generar_codigo_barras_svg(codigo_para_barras)
        lotes_con_svg.append({
            'lote': lote,
            'barcode_svg': barcode_svg,
            'esta_vencido': esta_vencido,
            'vence_pronto': vence_pronto,
        })

    return render(
        request,
        'panel/stock/etiquetaLote.html',
        {
            'lotes_con_svg': lotes_con_svg,
            'es_lote_individual': False,
            'autoprint': request.GET.get('autoprint') == '1',
        }
    )





def _leer_unidades_insumo(post):
    """Lee y valida unidad de ingreso, unidad de egreso y equivalencia manual."""
    ingreso = (post.get('unidadmedidaingreso') or '').strip()
    egreso = (post.get('unidadmedidaegreso') or '').strip()
    equiv_raw = (post.get('equivalencia_egreso') or '').strip().replace(',', '.')
    errores = []
    equivalencia = None

    if not ingreso or not egreso:
        errores.append('Completá las unidades de medida de ingreso y de egreso.')

    for etiqueta, unidad in (('ingreso', ingreso), ('egreso', egreso)):
        if unidad and (
            any(caracter.isdigit() for caracter in unidad)
            or not any(caracter.isalpha() for caracter in unidad)
        ):
            errores.append(
                f'La unidad de {etiqueta} no puede contener números '
                '(por ejemplo: kg, g, litro, unidad).'
            )

    if equiv_raw:
        try:
            equivalencia = Decimal(equiv_raw)
            if (
                not equivalencia.is_finite()
                or equivalencia <= 0
                or equivalencia.as_tuple().exponent < -4
            ):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            equivalencia = None
            errores.append(
                'La equivalencia debe ser un número mayor que cero, con hasta 4 decimales.'
            )

    if (
        ingreso and egreso and not equiv_raw
        and not unidades_compatibles(ingreso, egreso)
    ):
        errores.append(
            f'Las unidades "{ingreso}" y "{egreso}" no se pueden convertir solas. '
            f'Indicá cuántas "{egreso}" trae 1 "{ingreso}" en el campo de equivalencia.'
        )

    return ingreso, egreso, equivalencia, errores


def _leer_cantidad_stock(texto, defecto=Decimal('0')):
    """Cantidad >= 0 con hasta 4 decimales; si es inválida devuelve `defecto`."""
    try:
        valor = Decimal(str(texto or '').strip().replace(',', '.') or defecto)
        if not valor.is_finite() or valor < 0:
            return defecto
        return valor
    except (InvalidOperation, ValueError, TypeError):
        return defecto


def _leer_vencimiento(texto):
    """Devuelve (fecha | None, error | None). El campo es opcional."""
    texto = (texto or '').strip()
    if not texto:
        return None, None

    fecha = parse_date(texto)
    if fecha is None:
        return None, 'La fecha de vencimiento no es válida.'

    if fecha < timezone.localdate():
        return None, 'La fecha de vencimiento no puede ser anterior a hoy.'

    return fecha, None


def _buscar_insumo_duplicado(nombre, excluir_pk=None):
    """
    Devuelve el insumo existente con el mismo nombre (sin importar mayúsculas,
    tildes ni espacios sobrantes), o None si el nombre está libre.
    """
    clave = local_normalizar(' '.join((nombre or '').split()))
    if not clave:
        return None

    candidatos = Insumo.objects.all()
    if excluir_pk is not None:
        candidatos = candidatos.exclude(pk=excluir_pk)

    for existente in candidatos.only('idinsumo', 'nombreinsumo'):
        if local_normalizar(' '.join(existente.nombreinsumo.split())) == clave:
            return existente
    return None


def _contexto_form_insumo(extra=None):
    contexto = {'unidades_sugeridas': UNIDADES_SUGERIDAS}
    if extra:
        contexto.update(extra)
    return contexto


@panel_login_requerido
@requiere_permiso('stock.crear')
def stock_crear(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombreinsumo', '').strip()
        descontar_auto = request.POST.get('descontar_stock_automaticamente') == 'on'

        unidad_ingreso, unidad_egreso, equivalencia, errores = _leer_unidades_insumo(request.POST)

        if not nombre:
            errores.insert(0, 'Completá el nombre del insumo.')
        elif _buscar_insumo_duplicado(nombre):
            errores.insert(
                0,
                f'El insumo "{nombre}" ya existe en el stock. No se puede crear de nuevo: '
                'para sumar mercadería usá "Registrar compra".'
            )

        stock_inicial = _leer_cantidad_stock(request.POST.get('stockactual'))
        stock_minimo = _leer_cantidad_stock(
            request.POST.get('stockminimo'), Decimal('5')
        )

        vencimiento, error_vencimiento = _leer_vencimiento(
            request.POST.get('fechavencimiento')
        )
        if error_vencimiento and stock_inicial > 0:
            errores.append(error_vencimiento)

        if errores:
            for error in errores:
                messages.error(request, error)
            return render(
                request,
                'panel/stock/stockForm.html',
                _contexto_form_insumo({'datos': request.POST}),
            )

        with transaction.atomic():
            insumo = Insumo.objects.create(
                nombreinsumo=nombre,
                unidadmedidaingreso=unidad_ingreso,
                unidadmedidaegreso=unidad_egreso,
                equivalencia_egreso=equivalencia,
                stockactual=Decimal('0'),
                stockminimo=stock_minimo,
                descontar_stock_automaticamente=descontar_auto,
            )

            # Carga inicial: se registra como lote (con vencimiento) y movimiento propio.
            if stock_inicial > 0:
                registrar_ingreso_lote(
                    insumo,
                    stock_inicial,
                    vencimiento,
                    tipo_movimiento=TIPO_CARGA_INICIAL,
                    descripcion=f"Carga inicial de stock al crear el insumo '{insumo.nombreinsumo}'",
                )

        messages.success(request, 'Insumo creado correctamente en el stock.')
        return redirect('stock_lista')

    return render(request, 'panel/stock/stockForm.html', _contexto_form_insumo())


@panel_login_requerido
@requiere_permiso('stock.editar')
def stock_editar(request, idinsumo):
    insumo = get_object_or_404(Insumo, pk=idinsumo)

    if request.method == 'POST':
        nombre = request.POST.get('nombreinsumo', '').strip()
        unidad_ingreso, unidad_egreso, equivalencia, errores = _leer_unidades_insumo(request.POST)

        if not nombre:
            errores.insert(0, 'Completá el nombre del insumo.')
        elif _buscar_insumo_duplicado(nombre, excluir_pk=insumo.pk):
            errores.insert(
                0,
                f'Ya existe otro insumo llamado "{nombre}". Elegí un nombre distinto.'
            )

        if errores:
            for error in errores:
                messages.error(request, error)
            return render(
                request,
                'panel/stock/editarStock.html',
                _contexto_form_insumo({'insumo': insumo}),
            )

        unidad_cambio = normalizar_unidad(unidad_ingreso) != normalizar_unidad(
            insumo.unidadmedidaingreso
        )

        insumo.nombreinsumo = nombre
        insumo.unidadmedidaingreso = unidad_ingreso
        insumo.unidadmedidaegreso = unidad_egreso
        insumo.equivalencia_egreso = equivalencia
        insumo.stockminimo = _leer_cantidad_stock(
            request.POST.get('stockminimo'), Decimal('5')
        )
        insumo.descontar_stock_automaticamente = (
            request.POST.get('descontar_stock_automaticamente') == 'on'
        )

        # El stock NO se edita acá: se cambia con "Ajustar stock" para que los lotes cuadren.
        insumo.save(update_fields=[
            'nombreinsumo', 'unidadmedidaingreso', 'unidadmedidaegreso',
            'equivalencia_egreso', 'stockminimo', 'descontar_stock_automaticamente',
        ])

        messages.success(request, 'Insumo actualizado correctamente.')
        if unidad_cambio:
            messages.warning(
                request,
                'Cambiaste la unidad de ingreso: el stock y los lotes no se convierten '
                'solos. Revisá las cantidades con "Ajustar stock".'
            )
        return redirect('stock_lista')

    return render(
        request, 'panel/stock/editarStock.html', _contexto_form_insumo({'insumo': insumo})
    )


@panel_login_requerido
@requiere_permiso('stock.compras')
def registrar_compra_insumo(request):

    if request.method == 'POST':
        insumo_id = request.POST.get('idinsumo')

        try:
            cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
            precio_total = Decimal(request.POST.get('preciototal', '0').replace(',', '.'))

        except (InvalidOperation, ValueError, TypeError, AttributeError):
            messages.error(
                request,
                'Ingresá una cantidad y un precio total válidos.'
            )
            return redirect('registrar_compra_insumo')

        if (
            not cantidad.is_finite()
            or not precio_total.is_finite()
            or cantidad <= 0
            or precio_total < 0
        ):
            messages.error(
                request,
                'La cantidad debe ser mayor que cero y el precio total '
                'no puede ser negativo.'
            )
            return redirect('registrar_compra_insumo')

        vencimiento, error_vencimiento = _leer_vencimiento(
            request.POST.get('fechavencimiento')
        )
        if error_vencimiento:
            messages.error(request, error_vencimiento)
            return redirect('registrar_compra_insumo')

        costo_unitario = precio_total / cantidad

        fecha_compra = timezone.now()

        try:
            with transaction.atomic():

                insumo = get_object_or_404(
                    Insumo.objects.select_for_update(),
                    pk=insumo_id
                )

                compra = Compras.objects.create(
                    fecha=fecha_compra,
                    preciototal=precio_total,
                    idempleado=request.user if isinstance(request.user, Empleado) else None,
                )

                DetalleCompra.objects.create(
                    idcompra=compra,
                    idinsumo=insumo,
                    cantidad=cantidad,
                    costounitario=costo_unitario,
                )

                # Crea el lote (con su vencimiento), suma el stock y registra el movimiento.
                registrar_ingreso_lote(
                    insumo,
                    cantidad,
                    vencimiento,
                    tipo_movimiento=MovimientoStock.TIPO_COMPRA,
                    descripcion=f"Compra #{compra.idcompra} de {insumo.nombreinsumo}",
                )

        except Insumo.DoesNotExist:
            messages.error(request, 'El insumo seleccionado no existe.')
            return redirect('registrar_compra_insumo')

        messages.success(
            request,
            'Compra registrada correctamente. Se guardaron el precio total, '
            'el costo unitario, el lote con su vencimiento y el stock actualizado.'
        )

        return redirect('stock_lista')

    return render(request, 'panel/stock/registrarCompra.html', {
        'insumos': Insumo.objects.all().order_by('nombreinsumo'),
    })


@panel_login_requerido
@requiere_permiso('stock.ajustar')
def ajustar_stock(request, idinsumo):
    insumo = get_object_or_404(Insumo, pk=idinsumo)

    if request.method == 'POST':
        cantidad_nueva_texto = request.POST.get('cantidadnueva', '').strip().replace(',', '.')
        motivo = request.POST.get('motivo', '').strip()

        try:
            cantidad_nueva = Decimal(cantidad_nueva_texto)

            if not cantidad_nueva.is_finite() or cantidad_nueva < 0:
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                'Ingresá una cantidad válida, igual o mayor que cero.'
            )
            return redirect('ajustar_stock', idinsumo=idinsumo)

        if not motivo:
            messages.error(request, 'Debés indicar el motivo del ajuste.')
            return redirect('ajustar_stock', idinsumo=idinsumo)

        if len(motivo) > 250:
            messages.error(
                request,
                'El motivo no puede superar los 250 caracteres.'
            )
            return redirect('ajustar_stock', idinsumo=idinsumo)

        vencimiento, error_vencimiento = _leer_vencimiento(
            request.POST.get('fechavencimiento')
        )
        if error_vencimiento:
            messages.error(request, error_vencimiento)
            return redirect('ajustar_stock', idinsumo=idinsumo)

        # Stock que veía la persona al abrir el formulario (detecta cambios simultáneos).
        stock_esperado = None
        esperado_texto = request.POST.get('stock_esperado', '').strip().replace(',', '.')
        if esperado_texto:
            try:
                stock_esperado = Decimal(esperado_texto)
                if not stock_esperado.is_finite():
                    stock_esperado = None
            except (InvalidOperation, ValueError):
                stock_esperado = None

        # Mantiene sincronizados el stock del insumo y sus lotes.
        try:
            ajustar_stock_insumo(
                idinsumo, cantidad_nueva, motivo, vencimiento,
                empleado=request.user if isinstance(request.user, Empleado) else None,
                stock_esperado=stock_esperado,
            )
        except StockCambiadoError as error:
            messages.error(request, str(error))
            return redirect('ajustar_stock', idinsumo=idinsumo)

        messages.success(request, 'Stock ajustado correctamente.')
        return redirect('stock_lista')

    return render(request, 'panel/stock/ajustarStock.html', {
        'insumo': insumo,
    })


@panel_login_requerido
@requiere_permiso('stock.ajustar')
@require_POST
def lote_baja(request, idlote):
    """Descarta lo que queda de un lote (vencido o en mal estado) y lo resta del stock."""
    lote = get_object_or_404(Lote.objects.select_related('idinsumo'), pk=idlote)
    motivo = (request.POST.get('motivo') or '').strip()[:150] or (
        'Lote vencido' if lote.esta_vencido else 'Baja de lote'
    )

    _, cantidad = dar_baja_lote(lote.pk, motivo)

    if cantidad > 0:
        registrar_auditoria(
            request,
            'LOTE_BAJA',
            f'Baja del lote {lote.codigo} ({lote.idinsumo.nombreinsumo}): {cantidad} '
            f'{lote.idinsumo.unidadmedidaingreso}. Motivo: {motivo}',
        )
        messages.success(
            request,
            f'Se dio de baja el lote {lote.codigo}: se descontaron '
            f'{cantidad.normalize():f} {lote.idinsumo.unidadmedidaingreso} del stock.'
        )
    else:
        messages.info(request, 'Ese lote ya no tenía cantidad disponible.')

    return redirect('stock_lista')


# 9. PANEL - USUARIOS

def _error_correo(correo, idempleado=None):
    """Devuelve un mensaje de error o None si el correo es válido."""
    if not correo:
        return 'Debes indicar el correo electrónico.'

    if len(correo) > 254:
        return 'El correo no puede superar los 254 caracteres.'

    try:
        validate_email(correo)
    except ValidationError:
        return 'Ingresa un correo electrónico válido.'

    repetidos = Empleado.objects.filter(correo__iexact=correo)

    if idempleado is not None:
        repetidos = repetidos.exclude(pk=idempleado)

    if repetidos.exists():
        return 'Ya existe un usuario con ese correo.'

    return None


registrar_permiso('usuarios.crear')
registrar_permiso('roles.asignar_permisos')


@panel_login_requerido
@requiere_permiso('usuarios.ver')
def empleado_lista(request):
    if request.method == 'POST':
        if hasattr(request.user, 'tiene_permiso') and not request.user.tiene_permiso('usuarios.crear'):
            messages.error(request, 'No tenés permiso para crear usuarios.')
            return redirect('empleado_lista')
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        idrol = request.POST.get('idrol', '').strip()
        correo = request.POST.get('correo', '').strip().lower()
        contrasena = request.POST.get('contrasena', '')
        repetida = request.POST.get('confirmar_contrasena', '')

        if not nombre or not apellido:
            messages.error(request, 'Debes indicar el nombre y el apellido.')
            return redirect('empleado_lista')

        if len(nombre) > 100 or len(apellido) > 100:
            messages.error(
                request,
                'El nombre y el apellido no pueden superar los 100 caracteres.'
            )
            return redirect('empleado_lista')

        error_correo = _error_correo(correo)
        if error_correo:
            messages.error(request, error_correo)
            return redirect('empleado_lista')

        try:
            rol = Rol.objects.get(pk=idrol)
        except (Rol.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Selecciona un rol válido.')
            return redirect('empleado_lista')

        if not contrasena:
            messages.error(request, 'Debes indicar una contraseña.')
            return redirect('empleado_lista')

        if contrasena != repetida:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect('empleado_lista')

        error_contrasena = _error_contrasena_nueva(contrasena)
        if error_contrasena:
            messages.error(request, error_contrasena)
            return redirect('empleado_lista')

        with transaction.atomic():
            Empleado.objects.create(
                nombre=nombre,
                apellido=apellido,
                correo=correo,
                idrol=rol,
                contrasena=make_password(contrasena),
            )

        messages.success(request, 'Usuario creado correctamente.')
        return redirect('empleado_lista')

    empleados = Empleado.objects.order_by('apellido', 'nombre')

    return render(
        request,
        'panel/administracion/usuarios/empleadoLista.html',
        {
            'empleados': empleados,
            'roles': Rol.objects.all(),
        },
    )


@panel_login_requerido
@requiere_permiso('usuarios.crear')
def empleado_crear(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip().lower()
        idrol = request.POST.get('idrol', '').strip()
        contrasena = request.POST.get('contrasena', '')
        repetida = request.POST.get('confirmar_contrasena', '')

        if not nombre or not apellido:
            messages.error(request, 'Debes indicar el nombre y el apellido.')
            return redirect('empleado_crear')

        if len(nombre) > 100 or len(apellido) > 100:
            messages.error(
                request,
                'El nombre y el apellido no pueden superar los 100 caracteres.'
            )
            return redirect('empleado_crear')

        error_correo = _error_correo(correo)
        if error_correo:
            messages.error(request, error_correo)
            return redirect('empleado_crear')

        try:
            rol = Rol.objects.get(pk=idrol)
        except (Rol.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Seleccioná un rol válido.')
            return redirect('empleado_crear')

        if not contrasena:
            messages.error(request, 'Debes indicar una contraseña.')
            return redirect('empleado_crear')

        if contrasena != repetida:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect('empleado_crear')

        error_contrasena = _error_contrasena_nueva(contrasena)
        if error_contrasena:
            messages.error(request, error_contrasena)
            return redirect('empleado_crear')

        with transaction.atomic():
            Empleado.objects.create(
                nombre=nombre,
                apellido=apellido,
                correo=correo,
                idrol=rol,
                contrasena=make_password(contrasena),
            )

        messages.success(request, 'Usuario creado correctamente.')
        return redirect('empleado_lista')

    return render(
        request,
        'panel/administracion/usuarios/empleadoCrear.html',
        {'roles': Rol.objects.all()},
    )

@panel_login_requerido
@requiere_permiso('usuarios.editar')
def empleado_editar(request, idempleado):
    empleado = get_object_or_404(Empleado, pk=idempleado)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        idrol = request.POST.get('idrol', '').strip()
        correo = request.POST.get('correo', '').strip().lower()
        contrasena = request.POST.get('contrasena', '')
        repetida = request.POST.get('confirmar_contrasena', '')

        if not nombre or not apellido:
            messages.error(
                request,
                'Debes indicar el nombre y el apellido.'
            )
            return redirect(
                'empleado_editar',
                idempleado=empleado.pk
            )

        if len(nombre) > 100 or len(apellido) > 100:
            messages.error(
                request,
                'El nombre y el apellido no pueden superar los 100 caracteres.'
            )
            return redirect(
                'empleado_editar',
                idempleado=empleado.pk
            )

        error_correo = _error_correo(correo, empleado.pk)

        if error_correo:
            messages.error(request, error_correo)
            return redirect(
                'empleado_editar',
                idempleado=empleado.pk
            )

        try:
            rol = Rol.objects.get(pk=idrol)
        except (Rol.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Seleccioná un rol válido.')
            return redirect(
                'empleado_editar',
                idempleado=empleado.pk
            )

        if contrasena or repetida:
            if contrasena != repetida:
                messages.error(
                    request,
                    'Las contraseñas no coinciden.'
                )
                return redirect(
                    'empleado_editar',
                    idempleado=empleado.pk
                )

            error_contrasena = _error_contrasena_nueva(contrasena)
            if error_contrasena:
                messages.error(request, error_contrasena)
                return redirect(
                    'empleado_editar',
                    idempleado=empleado.pk
                )

        activo_check = request.POST.get('activo') is not None
        if getattr(request.user, 'pk', None) == empleado.pk and not activo_check:
            messages.error(request, 'Por motivos de seguridad no podés desactivar tu propia cuenta.')
            return redirect('empleado_editar', idempleado=empleado.pk)

        if (
            getattr(request.user, 'pk', None) == empleado.pk
            and hasattr(request.user, 'idrol')
            and request.user.idrol
            and (request.user.idrol.nombrerol or '').strip().lower() == 'administrador'
            and (rol.nombrerol or '').strip().lower() != 'administrador'
        ):
            messages.error(request, 'No podés remover tu propio rol de Administrador.')
            return redirect('empleado_editar', idempleado=empleado.pk)

        with transaction.atomic():
            empleado = Empleado.objects.select_for_update().get(
                pk=idempleado
            )

            empleado.nombre = nombre
            empleado.apellido = apellido
            empleado.correo = correo
            empleado.idrol = rol
            empleado.activo = activo_check

            campos = [
                'nombre',
                'apellido',
                'correo',
                'idrol',
                'activo',
            ]

            if contrasena:
                empleado.contrasena = make_password(contrasena)
                campos.append('contrasena')

            empleado.save(update_fields=campos)
            registrar_auditoria(request, 'USUARIO_EDITAR', f'Empleado {empleado.correo} modificado')

        messages.success(
            request,
            'Usuario actualizado correctamente.'
        )
        return redirect('empleado_lista')

    return render(
        request,
        'panel/administracion/usuarios/empleadoModificar.html',
        {
            'empleado': empleado,
            'roles': Rol.objects.all(),
        },
    )

@panel_login_requerido
@requiere_permiso('usuarios.eliminar')
def empleado_eliminar(request, idempleado):
    empleado = get_object_or_404(Empleado, pk=idempleado)

    # Si se confirma el formulario, se elimina el usuario.
    if request.method == 'POST':
        nombre_completo = f'{empleado.nombre} {empleado.apellido}'

        try:
            empleado.delete()

            messages.success(
                request,
                f'El usuario "{nombre_completo}" fue eliminado correctamente.'
            )

        except IntegrityError:
            messages.error(
                request,
                'No se puede eliminar este usuario porque tiene registros relacionados.'
            )

        return redirect('empleado_lista')

    # Si se ingresa mediante GET, muestra la página de confirmación.
    return render(
        request,
        'panel/administracion/usuarios/empleadoEliminar.html',
        {'empleado': empleado}
    )


# 10. PANEL - ROLES

@panel_login_requerido
@requiere_permiso('roles.ver')
def rol_lista(request):
    roles = Rol.objects.all().order_by('nombrerol')

    return render(
        request,
        'panel/administracion/roles/rolLista.html',
        {'roles': roles},
    )


def _asegurar_permisos_sincronizados():
    """Crea en la base los permisos nuevos antes de mostrarlos en los roles."""
    try:
        from core.permisos_config import sincronizar_permisos
        sincronizar_permisos()
    except Exception:
        logger.exception('No se pudieron sincronizar los permisos')


@panel_login_requerido
@requiere_permiso('roles.crear')
def rol_crear(request):
    _asegurar_permisos_sincronizados()
    permisos = Permiso.objects.all().order_by('modulo', 'accion')
    permisos_seleccionados = []

    if request.method == 'POST':
        nombre = request.POST.get('nombrerol', '').strip()

        for valor in request.POST.getlist('permisos'):
            try:
                permisos_seleccionados.append(int(valor))
            except (ValueError, TypeError):
                continue

        if not request.user.tiene_permiso('roles.asignar_permisos'):
            permisos_seleccionados = []

        if not nombre:
            messages.error(request, 'El nombre del rol es obligatorio.')

        elif len(nombre) > 50:
            messages.error(
                request,
                'El nombre del rol no puede superar los 50 caracteres.'
            )

        elif Rol.objects.filter(nombrerol__iexact=nombre).exists():
            messages.error(request, 'Ya existe un rol con ese nombre.')

        else:
            try:
                with transaction.atomic():
                    rol = Rol.objects.create(nombrerol=nombre)

                    permisos_validos = Permiso.objects.filter(
                        pk__in=permisos_seleccionados
                    )

                    RolPermiso.objects.bulk_create([
                        RolPermiso(
                            idrol=rol,
                            idpermiso=permiso
                        )
                        for permiso in permisos_validos
                    ])

                messages.success(
                    request,
                    'Rol creado y permisos asignados correctamente.'
                )
                return redirect('rol_lista')

            except Exception:
                logger.exception(
                    'Error al crear el rol "%s" y asignar sus permisos.',
                    nombre
                )
                messages.error(
                    request,
                    'No se pudo crear el rol. Revisa el error en la consola del servidor.'
                )

    return render(
        request,
        'panel/administracion/roles/rolCrear.html',
        {
            'titulo': 'Nuevo rol',
            'rol': None,
            'permisos': permisos,
            'permisos_seleccionados': permisos_seleccionados,
        }
    )


@panel_login_requerido
@requiere_permiso('roles.editar')
def rol_editar(request, idrol):
    rol = get_object_or_404(Rol, pk=idrol)

    _asegurar_permisos_sincronizados()
    permisos = Permiso.objects.all().order_by('modulo', 'accion')

    permisos_seleccionados = list(
        RolPermiso.objects.filter(
            idrol=rol
        ).values_list('idpermiso_id', flat=True)
    )

    if request.method == 'POST':
        nombre = request.POST.get('nombrerol', '').strip()

        ids_permisos = []

        for valor in request.POST.getlist('permisos'):
            try:
                ids_permisos.append(int(valor))
            except (ValueError, TypeError):
                continue

        if not request.user.tiene_permiso('roles.asignar_permisos'):
            ids_permisos = list(permisos_seleccionados)

        if not nombre:
            messages.error(request, 'El nombre del rol es obligatorio.')

        elif len(nombre) > 50:
            messages.error(
                request,
                'El nombre del rol no puede superar los 50 caracteres.'
            )

        elif Rol.objects.filter(
            nombrerol__iexact=nombre
        ).exclude(pk=rol.pk).exists():
            messages.error(request, 'Ya existe un rol con ese nombre.')

        else:
            try:
                with transaction.atomic():
                    rol.nombrerol = nombre
                    rol.save(update_fields=['nombrerol'])

                    permisos_validos = Permiso.objects.filter(
                        pk__in=ids_permisos
                    )

                    RolPermiso.objects.filter(idrol=rol).delete()

                    RolPermiso.objects.bulk_create([
                        RolPermiso(
                            idrol=rol,
                            idpermiso=permiso
                        )
                        for permiso in permisos_validos
                    ])

                messages.success(
                    request,
                    'Rol y permisos actualizados correctamente.'
                )
                return redirect('rol_lista')

            except Exception:
                logger.exception(
                    'Error al editar el rol "%s".',
                    nombre
                )
                messages.error(
                    request,
                    'No se pudo actualizar el rol y sus permisos. '
                    'Revisa la consola del servidor.'
                )

    return render(
        request,
        'panel/administracion/roles/rolEditar.html',
        {
            'titulo': 'Editar rol',
            'rol': rol,
            'permisos': permisos,
            'permisos_seleccionados': permisos_seleccionados,
        }
    )

@panel_login_requerido
@requiere_permiso('roles.eliminar')
@require_POST
def rol_eliminar(request, idrol):
    rol = get_object_or_404(Rol, pk=idrol)
    nombre = rol.nombrerol or f"Rol {rol.pk}"

    try:
        rol.delete()
        messages.success(
            request,
            f'El rol "{nombre}" se eliminó correctamente.'
        )
    except ProtectedError:
        messages.error(
            request,
            f'No se puede eliminar el rol "{nombre}" porque está '
            'asignado a empleados u otros registros relacionados.'
        )
    except Exception:
        messages.error(
            request,
            f'No se pudo eliminar el rol "{nombre}".'
        )

    return redirect('rol_lista')

@panel_login_requerido
@requiere_permiso('roles.ver')
def rol_permisos(request, idrol):
    return redirect('rol_editar', idrol=idrol)


# 10. PANEL - REPORTES

# 10.1 Constantes de diseño

BI_OSCURO = "17181D"
BI_ROJO = "D93632"
BI_GRIS = "6B7280"
BI_PALETA = [
    "D93632", "3B82F6", "10B981", "F59E0B",
    "8B5CF6", "F97316", "06B6D4", "EC4899",
]

# Colores del panel para el Excel
BI_XL_FONDO = "181818"
BI_XL_TARJETA = "202020"
BI_XL_CABECERA = "292929"
BI_XL_BORDE = "333333"
BI_XL_TEXTO = "F3F4F6"
BI_XL_APAGADO = "9CA3AF"
BI_XL_ROJO = "DC2626"

BI_FORMATO_XLSX = {
    "moneda": '"$" #,##0.00',
    "entero": "#,##0",
    "pct": '0.0"%"',
    "pct_signo": '+0.0"%";-0.0"%"',
    "fecha": "DD/MM/YYYY",
}
BI_NUMERICOS = {"moneda", "entero", "pct", "pct_signo"}

BI_DIAS_SEMANA = [
    "Lunes", "Martes", "Miércoles", "Jueves",
    "Viernes", "Sábado", "Domingo",
]


# 10.2 Utilidades de fechas y formato

def bi_fechas(request):
    """Lee y valida el rango de fechas enviado por el usuario."""
    hoy = timezone.localdate()
    inicio_default = hoy - timedelta(days=29)

    inicio = parse_date(request.GET.get("fecha_inicio", "")) or inicio_default
    fin = parse_date(request.GET.get("fecha_fin", "")) or hoy

    if inicio > fin:
        inicio, fin = fin, inicio

    return inicio, fin


def bi_contexto(inicio, fin):
    return {
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "periodo": f"{inicio:%d/%m/%Y} al {fin:%d/%m/%Y}",
    }


def bi_periodo_anterior(inicio, fin):
    """Período de igual duración inmediatamente anterior al actual."""
    duracion = (fin - inicio).days + 1
    fin_anterior = inicio - timedelta(days=1)
    inicio_anterior = fin_anterior - timedelta(days=duracion - 1)
    return inicio_anterior, fin_anterior, duracion


def bi_variacion(actual, anterior):
    """Variación porcentual; None si no hay base de comparación."""
    if anterior and anterior > 0:
        return (actual - anterior) / anterior * Decimal("100")
    return None


def bi_cero(valor):
    return valor if valor is not None else Decimal("0.00")


def bi_pct(parte, total):
    return float(parte / total * 100) if total else 0.0


def bi_numero(valor, decimales=0):
    """Formato argentino: 1.234,56"""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def bi_moneda(valor):
    return f"$ {bi_numero(bi_cero(valor), 2)}"


def bi_formatear(valor, formato=None):
    if valor is None or valor == "":
        return "—"
    if formato == "moneda":
        return bi_moneda(valor)
    if formato == "entero":
        return bi_numero(valor, 0)
    if formato == "pct":
        return f"{bi_numero(valor, 1)}%"
    if formato == "pct_signo":
        return f"{'+' if valor > 0 else ''}{bi_numero(valor, 1)}%"
    if formato == "fecha":
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def bi_valor_excel(valor):
    if valor is None:
        return "—"
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


# 10.3 Consultas base

def bi_pedidos_validos():
    """Pedidos no cancelados (base de las ventas)."""
    return (
        Pedido.objects
        .exclude(idestadopedido__descripcion="Cancelado")
        .filter(total__isnull=False)
    )


def bi_pedidos_periodo(inicio, fin):
    return bi_pedidos_validos().filter(
        fecha_creacion__date__gte=inicio,
        fecha_creacion__date__lte=fin,
    )


def bi_pedidos_pagados_validos():
    """Pedidos cobrados y no cancelados (base del dinero recaudado)."""
    return (
        Pedido.objects
        .filter(pagado=True, total__isnull=False)
        .exclude(idestadopedido__descripcion="Cancelado")
    )


def bi_pedidos_pagados_periodo(inicio, fin):
    return bi_pedidos_pagados_validos().filter(
        fecha_creacion__date__gte=inicio,
        fecha_creacion__date__lte=fin,
    )


# 10.4 Cálculos de cada reporte

def bi_resumen(inicio, fin):
    # Las ventas solo suman pedidos pagados (y no cancelados).
    pedidos = bi_pedidos_pagados_periodo(inicio, fin)

    indicadores = pedidos.aggregate(
        total_vendido=Sum("total"),
        cantidad_pedidos=Count("idpedido"),
        ticket_promedio=Avg("total"),
    )
    indicadores["total_vendido"] = bi_cero(indicadores["total_vendido"])
    indicadores["cantidad_pedidos"] = indicadores["cantidad_pedidos"] or 0
    indicadores["ticket_promedio"] = bi_cero(indicadores["ticket_promedio"])

    ventas_diarias = list(
        pedidos.annotate(dia=TruncDate("fecha_creacion"))
        .values("dia")
        .annotate(total=Sum("total"), pedidos=Count("idpedido"))
        .order_by("dia")
    )

    maximo = max(
        (bi_cero(venta["total"]) for venta in ventas_diarias),
        default=Decimal("0.00"),
    )

    for venta in ventas_diarias:
        venta["total"] = bi_cero(venta["total"])
        venta["pedidos"] = venta["pedidos"] or 0
        venta["ticket_promedio"] = (
            venta["total"] / venta["pedidos"]
            if venta["pedidos"]
            else Decimal("0.00")
        )
        venta["porcentaje"] = (
            float(venta["total"] / maximo * 100) if maximo > 0 else 0
        )

    return indicadores, ventas_diarias


def bi_metricas_adicionales(inicio, fin, indicadores, ventas_diarias):
    inicio_anterior, fin_anterior, duracion = bi_periodo_anterior(inicio, fin)

    total_anterior = bi_cero(
        bi_pedidos_pagados_periodo(inicio_anterior, fin_anterior)
        .aggregate(total=Sum("total"))["total"]
    )
    total_actual = indicadores["total_vendido"]

    pedidos_por_estado = list(
        Pedido.objects.filter(
            fecha_creacion__date__gte=inicio,
            fecha_creacion__date__lte=fin,
        )
        .values("idestadopedido__descripcion")
        .annotate(cantidad=Count("idpedido"))
        .order_by("idestadopedido__descripcion")
    )

    return {
        "total_anterior": total_anterior,
        "inicio_anterior": inicio_anterior,
        "fin_anterior": fin_anterior,
        "variacion_porcentual": bi_variacion(total_actual, total_anterior),
        "promedio_diario": (
            total_actual / Decimal(duracion) if duracion > 0 else Decimal("0.00")
        ),
        "mejor_dia": max(
            ventas_diarias, key=lambda venta: venta["total"], default=None
        ),
        "pedidos_por_estado": pedidos_por_estado,
    }


def bi_top_productos(inicio, fin):
    importe_linea = ExpressionWrapper(
        F("cantidad") * F("preciounitario"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )

    return list(
        DetallePedido.objects.filter(
            idpedido__in=bi_pedidos_periodo(inicio, fin),
        )
        .annotate(
            nombre_historico=Coalesce(
                "idproducto__nombre", "nombreproducto", Value("Producto eliminado")
            )
        )
        .values("idproducto_id", "nombre_historico")
        .annotate(unidades=Sum("cantidad"), ingresos=Sum(importe_linea))
        .order_by("-unidades", "-ingresos", "nombre_historico")[:10]
    )


def bi_totales_productos(productos):
    unidades = sum((p["unidades"] or 0) for p in productos)
    ingresos = sum(
        (bi_cero(p["ingresos"]) for p in productos), Decimal("0.00")
    )
    return unidades, ingresos


def bi_datos_dinero(inicio, fin):
    pedidos = bi_pedidos_pagados_periodo(inicio, fin)

    indicadores = pedidos.aggregate(
        importe_total=Sum("total"),
        cantidad_pedidos=Count("idpedido"),
        ticket_promedio=Avg("total"),
    )
    importe_total = bi_cero(indicadores["importe_total"])
    cantidad_pedidos = indicadores["cantidad_pedidos"] or 0
    ticket_promedio = bi_cero(indicadores["ticket_promedio"])

    inicio_anterior, fin_anterior, duracion = bi_periodo_anterior(inicio, fin)
    promedio_diario = (
        importe_total / Decimal(duracion) if duracion > 0 else Decimal("0.00")
    )

    # --- Serie diaria (incluye días sin cobros) ---
    consulta_diaria = list(
        pedidos.annotate(fecha=TruncDate("fecha_creacion"))
        .values("fecha")
        .annotate(importe=Sum("total"), cantidad=Count("idpedido"))
        .order_by("fecha")
    )
    por_fecha = {
        fila["fecha"]: fila for fila in consulta_diaria if fila["fecha"]
    }
    maximo = max(
        (bi_cero(fila["importe"]) for fila in consulta_diaria),
        default=Decimal("0.00"),
    )

    dias = []
    fecha = inicio
    while fecha <= fin:
        fila = por_fecha.get(fecha, {})
        importe = bi_cero(fila.get("importe"))
        dias.append({
            "fecha": fecha,
            "importe": importe,
            "cantidad": fila.get("cantidad") or 0,
            "porcentaje": float(importe / maximo * 100) if maximo > 0 else 0,
        })
        fecha += timedelta(days=1)

    dias_con_datos = [dia for dia in dias if dia["cantidad"] > 0]
    mejor_dia = max(dias_con_datos, key=lambda d: d["importe"], default=None)
    peor_dia = min(dias_con_datos, key=lambda d: d["importe"], default=None)

    # --- Por día de la semana ---
    agrupados = {
        indice: {"dia": nombre, "importe": Decimal("0.00"), "cantidad": 0}
        for indice, nombre in enumerate(BI_DIAS_SEMANA)
    }
    for dia in dias:
        indice = dia["fecha"].weekday()
        agrupados[indice]["importe"] += dia["importe"]
        agrupados[indice]["cantidad"] += dia["cantidad"]

    maximo_semana = max(
        (fila["importe"] for fila in agrupados.values()),
        default=Decimal("0.00"),
    )
    dias_semana = []
    for fila in agrupados.values():
        fila["porcentaje"] = (
            float(fila["importe"] / maximo_semana * 100)
            if maximo_semana > 0
            else 0
        )
        dias_semana.append(fila)

    mejor_dia_semana = max(
        dias_semana, key=lambda d: d["importe"], default=None
    )

    # --- Por medio de pago ---
    consulta_medios = list(
        pedidos.values("idmediopago__nombremetodo")
        .annotate(cantidad=Count("idpedido"), importe=Sum("total"))
        .order_by("-importe")
    )
    medios_pago = []
    for medio in consulta_medios:
        importe = bi_cero(medio["importe"])
        medios_pago.append({
            "nombre": medio["idmediopago__nombremetodo"] or "Sin medio de pago",
            "cantidad": medio["cantidad"],
            "importe": importe,
            "porcentaje": bi_pct(importe, importe_total),
        })

    # --- Comparación con el período anterior ---
    importe_anterior = bi_cero(
        bi_pedidos_pagados_periodo(inicio_anterior, fin_anterior)
        .aggregate(total=Sum("total"))["total"]
    )

    return {
        "importe_total": importe_total,
        "cantidad_pedidos": cantidad_pedidos,
        "ticket_promedio": ticket_promedio,
        "promedio_diario": promedio_diario,
        "dias": dias,
        "mejor_dia": mejor_dia,
        "peor_dia": peor_dia,
        "dias_semana": dias_semana,
        "mejor_dia_semana": mejor_dia_semana,
        "medios_pago": medios_pago,
        "variacion_porcentual": bi_variacion(importe_total, importe_anterior),
        "importe_anterior": importe_anterior,
        "inicio_anterior": inicio_anterior,
        "fin_anterior": fin_anterior,
    }


# 10.5 Definición de los reportes exportables
#      (misma estructura para Excel y PDF)

def bi_reporte_ventas(inicio, fin):
    indicadores, ventas = bi_resumen(inicio, fin)
    extra = bi_metricas_adicionales(inicio, fin, indicadores, ventas)
    total = indicadores["total_vendido"]
    mejor = extra["mejor_dia"]
    anterior = f"{extra['inicio_anterior']:%d/%m} al {extra['fin_anterior']:%d/%m}"

    estados = [
        (fila["idestadopedido__descripcion"] or "Sin estado", fila["cantidad"])
        for fila in extra["pedidos_por_estado"]
    ]
    total_estados = sum(cantidad for _, cantidad in estados)

    return {
        "titulo": "Resumen de ventas",
        "periodo": f"{inicio:%d/%m/%Y} al {fin:%d/%m/%Y}",
        "kpis": [
            {"titulo": "Total vendido", "valor": total, "formato": "moneda",
             "detalle": "Pedidos pagados"},
            {"titulo": "Pedidos", "valor": indicadores["cantidad_pedidos"],
             "formato": "entero", "detalle": "Operaciones del período"},
            {"titulo": "Ticket promedio", "valor": indicadores["ticket_promedio"],
             "formato": "moneda", "detalle": "Importe por pedido"},
            {"titulo": "Promedio diario", "valor": extra["promedio_diario"],
             "formato": "moneda", "detalle": "Ventas por día"},
            {"titulo": "Variación", "valor": extra["variacion_porcentual"],
             "formato": "pct_signo", "detalle": f"vs. {anterior}"},
            {"titulo": "Mejor día", "valor": mejor["dia"] if mejor else None,
             "formato": "fecha",
             "detalle": bi_moneda(mejor["total"]) if mejor else "Sin ventas"},
        ],
        "graficos": [
            {"tipo": "linea", "titulo": "Evolución de ventas por día",
             "etiquetas": [f"{v['dia']:%d/%m}" for v in ventas],
             "valores": [v["total"] for v in ventas]},
            {"tipo": "barras", "titulo": "Pedidos por día",
             "etiquetas": [f"{v['dia']:%d/%m}" for v in ventas],
             "valores": [v["pedidos"] for v in ventas]},
            {"tipo": "torta", "titulo": "Pedidos por estado (incluye cancelados)",
             "etiquetas": [e for e, _ in estados],
             "valores": [c for _, c in estados]},
        ],
        "tablas": [
            {
                "titulo": "Detalle diario de ventas",
                "encabezados": ["Fecha", "Pedidos", "Ticket promedio",
                                "Total vendido", "% del período"],
                "formatos": ["fecha", "entero", "moneda", "moneda", "pct"],
                "filas": [
                    [v["dia"], v["pedidos"], v["ticket_promedio"], v["total"],
                     bi_pct(v["total"], total)]
                    for v in ventas
                ],
            },
            {
                "titulo": "Pedidos por estado",
                "encabezados": ["Estado", "Pedidos", "% del total"],
                "formatos": [None, "entero", "pct"],
                "filas": [[e, c, bi_pct(c, total_estados)] for e, c in estados],
            },
        ],
    }


def bi_reporte_productos(inicio, fin):
    productos = bi_top_productos(inicio, fin)
    unidades_total, ingresos_total = bi_totales_productos(productos)

    lider = productos[0] if productos else None
    mayor_ingreso = max(
        productos, key=lambda p: bi_cero(p["ingresos"]), default=None
    )
    precio_promedio = (
        ingresos_total / unidades_total if unidades_total else Decimal("0.00")
    )
    nombres = [p["nombre_historico"] or "Sin nombre" for p in productos]

    return {
        "titulo": "Productos más vendidos",
        "periodo": f"{inicio:%d/%m/%Y} al {fin:%d/%m/%Y}",
        "kpis": [
            {"titulo": "Unidades (Top 10)", "valor": unidades_total,
             "formato": "entero", "detalle": "Suma del ranking"},
            {"titulo": "Ingresos (Top 10)", "valor": ingresos_total,
             "formato": "moneda", "detalle": "Suma del ranking"},
            {"titulo": "Precio promedio", "valor": precio_promedio,
             "formato": "moneda", "detalle": "Ingreso por unidad"},
            {"titulo": "Más vendido",
             "valor": lider["nombre_historico"] if lider else None,
             "formato": None,
             "detalle": f"{lider['unidades']} unidades" if lider else "Sin datos"},
            {"titulo": "Peso del líder",
             "valor": bi_pct(lider["unidades"], unidades_total) if lider else None,
             "formato": "pct", "detalle": "% de unidades del Top 10"},
            {"titulo": "Mayor ingreso",
             "valor": mayor_ingreso["nombre_historico"] if mayor_ingreso else None,
             "formato": None,
             "detalle": bi_moneda(mayor_ingreso["ingresos"]) if mayor_ingreso else "Sin datos"},
        ],
        "graficos": [
            {"tipo": "barras_h", "titulo": "Unidades vendidas por producto",
             "etiquetas": nombres,
             "valores": [p["unidades"] or 0 for p in productos]},
            {"tipo": "barras_h", "titulo": "Ingresos por producto",
             "etiquetas": nombres,
             "valores": [bi_cero(p["ingresos"]) for p in productos]},
        ],
        "tablas": [
            {
                "titulo": "Ranking detallado (participación sobre el Top 10)",
                "encabezados": ["#", "Producto", "Unidades", "% unidades",
                                "Ingresos", "% ingresos", "Precio promedio"],
                "formatos": ["entero", None, "entero", "pct",
                             "moneda", "pct", "moneda"],
                "filas": [
                    [
                        posicion,
                        nombre,
                        p["unidades"] or 0,
                        bi_pct(p["unidades"] or 0, unidades_total),
                        bi_cero(p["ingresos"]),
                        bi_pct(bi_cero(p["ingresos"]), ingresos_total),
                        (
                            bi_cero(p["ingresos"]) / p["unidades"]
                            if p["unidades"]
                            else Decimal("0.00")
                        ),
                    ]
                    for posicion, (nombre, p) in enumerate(
                        zip(nombres, productos), start=1
                    )
                ],
            }
        ],
    }


def bi_reporte_dinero(inicio, fin):
    d = bi_datos_dinero(inicio, fin)
    total = d["importe_total"]
    mejor = d["mejor_dia"]
    anterior = f"{d['inicio_anterior']:%d/%m} al {d['fin_anterior']:%d/%m}"

    return {
        "titulo": "Dinero recaudado",
        "periodo": f"{inicio:%d/%m/%Y} al {fin:%d/%m/%Y}",
        "kpis": [
            {"titulo": "Recaudación total", "valor": total,
             "formato": "moneda", "detalle": "Pedidos pagados"},
            {"titulo": "Pedidos cobrados", "valor": d["cantidad_pedidos"],
             "formato": "entero", "detalle": "Operaciones pagadas"},
            {"titulo": "Ticket promedio", "valor": d["ticket_promedio"],
             "formato": "moneda", "detalle": "Importe por pedido"},
            {"titulo": "Promedio diario", "valor": d["promedio_diario"],
             "formato": "moneda", "detalle": "Cobrado por día"},
            {"titulo": "Variación", "valor": d["variacion_porcentual"],
             "formato": "pct_signo", "detalle": f"vs. {anterior}"},
            {"titulo": "Mejor día", "valor": mejor["fecha"] if mejor else None,
             "formato": "fecha",
             "detalle": bi_moneda(mejor["importe"]) if mejor else "Sin cobros"},
        ],
        "graficos": [
            {"tipo": "linea", "titulo": "Recaudación por día",
             "etiquetas": [f"{x['fecha']:%d/%m}" for x in d["dias"]],
             "valores": [x["importe"] for x in d["dias"]]},
            {"tipo": "torta", "titulo": "Recaudación por medio de pago",
             "etiquetas": [m["nombre"] for m in d["medios_pago"]],
             "valores": [m["importe"] for m in d["medios_pago"]]},
            {"tipo": "barras", "titulo": "Recaudación por día de la semana",
             "etiquetas": [s["dia"] for s in d["dias_semana"]],
             "valores": [s["importe"] for s in d["dias_semana"]]},
        ],
        "tablas": [
            {
                "titulo": "Detalle por medio de pago",
                "encabezados": ["Medio de pago", "Pedidos", "Importe", "% del total"],
                "formatos": [None, "entero", "moneda", "pct"],
                "filas": [
                    [m["nombre"], m["cantidad"], m["importe"], m["porcentaje"]]
                    for m in d["medios_pago"]
                ],
            },
            {
                "titulo": "Rendimiento por día de la semana",
                "encabezados": ["Día", "Pedidos", "Importe", "% del total"],
                "formatos": [None, "entero", "moneda", "pct"],
                "filas": [
                    [s["dia"], s["cantidad"], s["importe"],
                     bi_pct(s["importe"], total)]
                    for s in d["dias_semana"]
                ],
            },
            {
                "titulo": "Detalle diario",
                "encabezados": ["Fecha", "Pedidos cobrados", "Recaudación"],
                "formatos": ["fecha", "entero", "moneda"],
                "filas": [
                    [x["fecha"], x["cantidad"], x["importe"]]
                    for x in d["dias"]
                    if x["cantidad"]
                ],
            },
        ],
    }


# 10.6 Exportación a Excel

def bi_celda(hoja, rango, valor, fuente, relleno=None,
             alineacion=None, formato=None):
    hoja.merge_cells(rango)
    celda = hoja[rango.split(":")[0]]
    celda.value = valor
    celda.font = fuente
    if relleno:
        celda.fill = PatternFill("solid", fgColor=relleno)
    celda.alignment = alineacion or Alignment(
        horizontal="left", vertical="center", indent=1
    )
    if formato:
        celda.number_format = formato
    return celda


def bi_estilo_grafico_excel(objeto):
    """Gráfico oscuro, con los mismos colores que el panel."""
    from openpyxl.chart.shapes import GraphicalProperties as GP
    from openpyxl.chart.text import RichText
    from openpyxl.drawing.line import LineProperties
    from openpyxl.drawing.text import CharacterProperties, Paragraph, ParagraphProperties

    def texto(tamano=900, negrita=False, color=BI_XL_TEXTO):
        propiedades = CharacterProperties(sz=tamano, b=negrita, solidFill=color)
        return RichText(p=[Paragraph(
            pPr=ParagraphProperties(defRPr=propiedades), endParaRPr=propiedades
        )])

    objeto.graphical_properties = GP(
        solidFill=BI_XL_TARJETA, ln=LineProperties(solidFill=BI_XL_BORDE)
    )
    objeto.plot_area.graphicalProperties = GP(noFill=True)

    if objeto.title is not None and objeto.title.tx is not None and objeto.title.tx.rich:
        propiedades = CharacterProperties(sz=1200, b=True, solidFill=BI_XL_TEXTO)
        for parrafo in objeto.title.tx.rich.p:
            parrafo.pPr = ParagraphProperties(defRPr=propiedades)
            for tramo in parrafo.r or []:
                tramo.rPr = propiedades

    if objeto.legend is not None:
        objeto.legend.txPr = texto()

    for eje in (getattr(objeto, "x_axis", None), getattr(objeto, "y_axis", None)):
        if eje is None:
            continue
        eje.txPr = texto()
        eje.graphicalProperties = GP(ln=LineProperties(solidFill=BI_XL_BORDE))
        if eje.majorGridlines is not None:
            eje.majorGridlines.spPr = GP(ln=LineProperties(solidFill=BI_XL_CABECERA))

    if getattr(objeto, "dataLabels", None) is not None:
        objeto.dataLabels.txPr = texto(900, True, "FFFFFF")


def bi_grafico_excel(grafico, datos, indice):
    etiquetas = grafico["etiquetas"]
    valores = grafico["valores"]
    cantidad = len(etiquetas)
    if cantidad == 0 or not any(valores):
        return None

    columna = indice * 3 + 1
    datos.cell(row=1, column=columna, value="Etiqueta")
    datos.cell(row=1, column=columna + 1, value=grafico["titulo"])
    for numero, (etiqueta, valor) in enumerate(zip(etiquetas, valores), start=2):
        datos.cell(row=numero, column=columna, value=str(etiqueta))
        datos.cell(row=numero, column=columna + 1, value=float(valor))

    categorias = Reference(datos, min_col=columna, min_row=2, max_row=cantidad + 1)
    serie = Reference(datos, min_col=columna + 1, min_row=1, max_row=cantidad + 1)
    tipo = grafico["tipo"]

    if tipo == "torta":
        objeto = PieChart()
        objeto.add_data(serie, titles_from_data=True)
        objeto.set_categories(categorias)
        objeto.dataLabels = DataLabelList()
        objeto.dataLabels.showPercent = True
        objeto.dataLabels.showVal = False
        objeto.dataLabels.showCatName = False
        objeto.dataLabels.showSerName = False
        objeto.dataLabels.showLeaderLines = False
        for posicion in range(cantidad):
            objeto.series[0].dPt.append(
                DataPoint(
                    idx=posicion,
                    spPr=GraphicalProperties(
                        solidFill=BI_PALETA[posicion % len(BI_PALETA)]
                    ),
                )
            )
    else:
        objeto = LineChart() if tipo == "linea" else BarChart()
        if tipo != "linea":
            objeto.type = "bar" if tipo == "barras_h" else "col"
            objeto.gapWidth = 60
        objeto.add_data(serie, titles_from_data=True)
        objeto.set_categories(categorias)
        objeto.legend = None
        objeto.x_axis.delete = False
        objeto.y_axis.delete = False
        objeto.y_axis.number_format = "#,##0"

        s = objeto.series[0]
        if tipo == "linea":
            s.smooth = True
            s.graphicalProperties.line.solidFill = BI_XL_ROJO
            s.graphicalProperties.line.width = 28575
            s.marker = Marker(
                symbol="circle", size=6,
                spPr=GraphicalProperties(solidFill=BI_XL_ROJO),
            )
        else:
            s.graphicalProperties.solidFill = BI_XL_ROJO

        if tipo == "barras_h":
            objeto.x_axis.scaling.orientation = "maxMin"  # el #1 arriba
            objeto.y_axis.crosses = "max"                 # eje de valores abajo

    objeto.title = grafico["titulo"]
    objeto.width = 16
    objeto.height = 7.5
    bi_estilo_grafico_excel(objeto)
    return objeto


def bi_exportar_excel(reporte, nombre_archivo):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"
    hoja.sheet_view.showGridLines = False
    hoja.sheet_view.zoomScale = 90
    hoja.sheet_properties.tabColor = BI_XL_ROJO
    datos = libro.create_sheet("Datos")

    COLUMNAS = 12
    ultima = get_column_letter(COLUMNAS)
    for numero in range(1, COLUMNAS + 1):
        hoja.column_dimensions[get_column_letter(numero)].width = 14

    graficos = reporte.get("graficos", [])
    filas_graficos = ((len(graficos) + 1) // 2) * 17
    filas_tablas = sum(len(t["filas"]) + 4 for t in reporte.get("tablas", []))
    total_filas = 9 + filas_graficos + filas_tablas + 4

    # ---------- Fondo oscuro, igual que el panel ----------
    fondo = PatternFill("solid", fgColor=BI_XL_FONDO)
    for fila_fondo in range(1, total_filas + 1):
        for numero in range(1, COLUMNAS + 1):
            hoja.cell(row=fila_fondo, column=numero).fill = fondo

    # ---------- Encabezado ----------
    banda = PatternFill("solid", fgColor=BI_XL_TARJETA)
    for fila in (1, 2, 3):
        for numero in range(1, COLUMNAS + 1):
            celda = hoja.cell(row=fila, column=numero)
            celda.fill = banda
            if fila == 3:
                celda.border = Border(bottom=Side(style="thick", color=BI_XL_ROJO))
    logo = hoja[f"A1"]
    hoja.merge_cells(f"A1:{ultima}1")
    logo.value = CellRichText(
        TextBlock(InlineFont(b=True, sz=20, color="FFFFFF"), "ZONA "),
        TextBlock(InlineFont(b=True, sz=20, color=BI_XL_ROJO), "BURGER"),
    )
    logo.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    bi_celda(hoja, f"A2:{ultima}2", reporte["titulo"],
             Font(bold=True, size=13, color="FFFFFF"), BI_XL_TARJETA)
    bi_celda(
        hoja, f"A3:{ultima}3",
        f"Período: {reporte['periodo']}   |   "
        f"Generado el {timezone.localdate():%d/%m/%Y}",
        Font(size=10, color=BI_XL_APAGADO), BI_XL_TARJETA,
    )
    hoja.row_dimensions[1].height = 34
    hoja.row_dimensions[2].height = 22
    hoja.row_dimensions[3].height = 20

    # ---------- Tarjetas de KPI ----------
    lado = Side(style="thin", color=BI_XL_BORDE)
    for indice, kpi in enumerate(reporte["kpis"][:6]):
        c1 = get_column_letter(indice * 2 + 1)
        c2 = get_column_letter(indice * 2 + 2)
        formato = kpi.get("formato")
        valor = bi_valor_excel(kpi["valor"])

        titulo_kpi = bi_celda(
            hoja, f"{c1}5:{c2}5", kpi["titulo"].upper(),
            Font(bold=True, size=8, color=BI_XL_APAGADO), BI_XL_TARJETA,
        )
        numero_kpi = bi_celda(
            hoja, f"{c1}6:{c2}6", valor,
            Font(bold=True, size=18, color="FFFFFF"), BI_XL_TARJETA,
            formato=BI_FORMATO_XLSX.get(formato),
        )
        detalle_kpi = bi_celda(
            hoja, f"{c1}7:{c2}7", kpi.get("detalle", ""),
            Font(size=8, color=BI_XL_APAGADO), BI_XL_TARJETA,
        )
        # Marco de la tarjeta con borde superior rojo; el espacio entre tarjetas es el fondo
        for fila_k, superior in ((5, Side(style="thick", color=BI_XL_ROJO)), (6, None), (7, lado)):
            for columna_k, izq, der in ((c1, lado, None), (c2, None, lado)):
                hoja[f"{columna_k}{fila_k}"].border = Border(
                    left=izq, right=der,
                    top=superior if superior else None,
                    bottom=lado if fila_k == 7 else None,
                )
    hoja.row_dimensions[5].height = 20
    hoja.row_dimensions[6].height = 36
    hoja.row_dimensions[7].height = 18

    # ---------- Gráficos (2 por fila) ----------
    fila = 9
    for indice, grafico in enumerate(graficos):
        objeto = bi_grafico_excel(grafico, datos, indice)
        if objeto is None:
            continue
        columna = "A" if indice % 2 == 0 else "G"
        hoja.add_chart(objeto, f"{columna}{fila + (indice // 2) * 17}")
    fila += filas_graficos + 1

    # ---------- Tablas ----------
    for tabla in reporte.get("tablas", []):
        encabezados = tabla["encabezados"]
        formatos = tabla.get("formatos") or [None] * len(encabezados)
        ancho = max(len(encabezados), 2)

        titulo_tabla = bi_celda(
            hoja, f"A{fila}:{get_column_letter(ancho)}{fila}",
            tabla["titulo"].upper(),
            Font(bold=True, size=11, color="FFFFFF"), BI_XL_TARJETA,
        )
        for numero in range(1, ancho + 1):
            hoja.cell(row=fila, column=numero).fill = banda
        hoja.cell(row=fila, column=1).border = Border(
            left=Side(style="thick", color=BI_XL_ROJO)
        )
        hoja.row_dimensions[fila].height = 22
        fila += 1

        for numero, encabezado in enumerate(encabezados, start=1):
            celda = hoja.cell(row=fila, column=numero, value=encabezado)
            celda.font = Font(bold=True, size=10, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor=BI_XL_CABECERA)
            celda.border = Border(bottom=Side(style="medium", color=BI_XL_ROJO))
            celda.alignment = Alignment(
                horizontal="right" if formatos[numero - 1] in BI_NUMERICOS else "left",
                vertical="center",
                wrap_text=True,
                indent=1,
            )
        hoja.row_dimensions[fila].height = 22
        fila += 1

        borde = Border(bottom=Side(style="thin", color=BI_XL_BORDE))
        for posicion, datos_fila in enumerate(tabla["filas"]):
            for numero, valor in enumerate(datos_fila, start=1):
                formato = formatos[numero - 1]
                celda = hoja.cell(row=fila, column=numero, value=bi_valor_excel(valor))
                if formato in BI_FORMATO_XLSX:
                    celda.number_format = BI_FORMATO_XLSX[formato]
                celda.font = Font(size=10, color=BI_XL_TEXTO)
                celda.alignment = Alignment(
                    horizontal="right" if formato in BI_NUMERICOS else "left",
                    vertical="center",
                    indent=1,
                )
                celda.border = borde
                celda.fill = PatternFill(
                    "solid", fgColor=BI_XL_TARJETA if posicion % 2 == 0 else BI_XL_FONDO
                )
            fila += 1
        fila += 2

    # ---------- Impresión ----------
    datos.sheet_state = "hidden"
    hoja.page_setup.orientation = "landscape"
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    buffer = BytesIO()
    libro.save(buffer)
    respuesta = HttpResponse(
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


# 10.7 Exportación a PDF

def bi_dibujo_grafico(grafico, ancho, alto):
    dibujo = Drawing(ancho, alto)
    rojo = colors.HexColor("#" + BI_ROJO)
    etiquetas = [str(e) for e in grafico["etiquetas"]]
    valores = [float(v) for v in grafico["valores"]]

    if not valores or not any(valores):
        dibujo.add(String(
            ancho / 2, alto / 2, "Sin datos para el período",
            textAnchor="middle", fontSize=9,
            fillColor=colors.HexColor("#" + BI_GRIS),
        ))
        return dibujo

    tipo = grafico["tipo"]

    if tipo == "torta":
        torta = Pie()
        torta.width = torta.height = alto - 50
        torta.x = ancho * 0.30
        torta.y = 20
        torta.data = valores
        torta.labels = [e[:22] for e in etiquetas]
        torta.sideLabels = True
        torta.slices.strokeColor = colors.white
        torta.slices.strokeWidth = 1
        torta.slices.fontSize = 7
        for posicion in range(len(valores)):
            torta.slices[posicion].fillColor = colors.HexColor(
                "#" + BI_PALETA[posicion % len(BI_PALETA)]
            )
        dibujo.add(torta)
        return dibujo

    if tipo == "barras_h":
        graf = HorizontalBarChart()
        graf.x, graf.y = 115, 10
        graf.width, graf.height = ancho - 135, alto - 20
        graf.data = [list(reversed(valores))]
        graf.categoryAxis.categoryNames = [e[:20] for e in reversed(etiquetas)]
        graf.categoryAxis.labels.fontSize = 7
        graf.valueAxis.labels.fontSize = 7
        graf.valueAxis.valueMin = 0
        graf.bars[0].fillColor = rojo
        graf.bars[0].strokeColor = None
        dibujo.add(graf)
        return dibujo

    graf = HorizontalLineChart() if tipo == "linea" else VerticalBarChart()
    graf.x, graf.y = 50, 35
    graf.width, graf.height = ancho - 70, alto - 50
    graf.data = [valores]
    paso = max(1, len(etiquetas) // 10)
    graf.categoryAxis.categoryNames = [
        e if i % paso == 0 else "" for i, e in enumerate(etiquetas)
    ]
    graf.categoryAxis.labels.fontSize = 7
    graf.categoryAxis.labels.angle = 30
    graf.categoryAxis.labels.boxAnchor = "ne"
    graf.valueAxis.labels.fontSize = 7
    graf.valueAxis.valueMin = 0
    graf.valueAxis.visibleGrid = True
    graf.valueAxis.gridStrokeColor = colors.HexColor("#E5E7EB")
    if tipo == "linea":
        graf.lines[0].strokeColor = rojo
        graf.lines[0].strokeWidth = 2
        graf.lines[0].symbol = makeMarker("Circle")
    else:
        graf.bars[0].fillColor = rojo
        graf.bars[0].strokeColor = None
    dibujo.add(graf)
    return dibujo


def bi_marco_pdf(titulo, periodo):
    """Cabecera y pie que se repiten en todas las páginas."""
    def dibujar(canvas, documento):
        ancho, alto = landscape(A4)
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#" + BI_OSCURO))
        canvas.rect(0, alto - 22 * mm, ancho, 22 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#" + BI_ROJO))
        canvas.rect(0, alto - 22 * mm, 6 * mm, 22 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(15 * mm, alto - 10 * mm, "ZONA BURGER")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(15 * mm, alto - 16.5 * mm, titulo)
        canvas.drawRightString(ancho - 15 * mm, alto - 10 * mm, f"Período: {periodo}")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            ancho - 15 * mm, alto - 16.5 * mm,
            f"Generado el {timezone.localdate():%d/%m/%Y}",
        )
        canvas.setFillColor(colors.HexColor("#" + BI_GRIS))
        canvas.drawString(15 * mm, 8 * mm, "Zona Burger · Reporte de gestión")
        canvas.drawRightString(ancho - 15 * mm, 8 * mm, f"Página {documento.page}")
        canvas.restoreState()
    return dibujar


def bi_exportar_pdf(reporte, nombre_archivo):
    respuesta = HttpResponse(content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'

    pagina = landscape(A4)
    ancho_total = pagina[0] - 30 * mm
    documento = SimpleDocTemplate(
        respuesta, pagesize=pagina,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=30 * mm, bottomMargin=16 * mm,
    )

    oscuro = colors.HexColor("#" + BI_OSCURO)
    rojo = colors.HexColor("#" + BI_ROJO)
    borde = colors.HexColor("#E5E7EB")
    gris = colors.HexColor("#9CA3AF")
    base = getSampleStyleSheet()["Normal"]

    est_kpi_titulo = ParagraphStyle("kpiT", parent=base, fontSize=7,
                                    leading=9, textColor=gris)
    est_kpi_valor = ParagraphStyle("kpiV", parent=base, fontName="Helvetica-Bold",
                                   fontSize=14, leading=18, textColor=colors.white)
    est_kpi_detalle = ParagraphStyle("kpiD", parent=base, fontSize=7,
                                     leading=9, textColor=gris)
    est_seccion = ParagraphStyle("sec", parent=base, fontName="Helvetica-Bold",
                                 fontSize=11, leading=14, textColor=oscuro,
                                 spaceBefore=10, spaceAfter=4, keepWithNext=1)
    est_grafico = ParagraphStyle("gra", parent=base, fontName="Helvetica-Bold",
                                 fontSize=9, leading=12, textColor=oscuro)
    est_celda = ParagraphStyle("cel", parent=base, fontSize=8, leading=10)
    est_celda_der = ParagraphStyle("celd", parent=est_celda, alignment=TA_RIGHT)
    est_enc = ParagraphStyle("enc", parent=est_celda, fontName="Helvetica-Bold",
                             textColor=colors.white)
    est_enc_der = ParagraphStyle("encd", parent=est_enc, alignment=TA_RIGHT)

    elementos = []

    # ---------- Tarjetas de KPI ----------
    kpis = reporte["kpis"][:6]
    celdas = [
        [
            Paragraph(escape(kpi["titulo"].upper()), est_kpi_titulo),
            Paragraph(
                escape(bi_formatear(kpi["valor"], kpi.get("formato"))),
                est_kpi_valor,
            ),
            Paragraph(escape(kpi.get("detalle", "")), est_kpi_detalle),
        ]
        for kpi in kpis
    ]
    tarjetas = Table([celdas], colWidths=[ancho_total / len(celdas)] * len(celdas))
    tarjetas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), oscuro),
        ("LINEABOVE", (0, 0), (-1, 0), 3, rojo),
        ("LINEAFTER", (0, 0), (-2, -1), 3, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos += [tarjetas, Spacer(1, 6 * mm)]

    # ---------- Gráficos (2 por fila) ----------
    graficos = reporte.get("graficos", [])
    ancho_col = (ancho_total - 8) / 2
    for inicio_fila in range(0, len(graficos), 2):
        grupo = graficos[inicio_fila:inicio_fila + 2]
        fila = [
            [
                Paragraph(escape(grafico["titulo"]), est_grafico),
                bi_dibujo_grafico(grafico, ancho_col - 14, 175),
            ]
            for grafico in grupo
        ]
        while len(fila) < 2:
            fila.append("")

        tabla_graficos = Table(
            [[fila[0], "", fila[1]]],
            colWidths=[ancho_col, 8, ancho_col],
        )
        estilo = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (1, 0), (1, 0), 0),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("BOX", (0, 0), (0, 0), 0.6, borde),
        ]
        if len(grupo) == 2:
            estilo.append(("BOX", (2, 0), (2, 0), 0.6, borde))
        tabla_graficos.setStyle(TableStyle(estilo))
        elementos += [tabla_graficos, Spacer(1, 4 * mm)]

    # ---------- Tablas ----------
    for tabla in reporte.get("tablas", []):
        encabezados = tabla["encabezados"]
        formatos = tabla.get("formatos") or [None] * len(encabezados)
        derecha = [formato in BI_NUMERICOS for formato in formatos]

        datos_tabla = [[
            Paragraph(escape(enc), est_enc_der if derecha[i] else est_enc)
            for i, enc in enumerate(encabezados)
        ]]
        for fila in tabla["filas"]:
            datos_tabla.append([
                Paragraph(
                    escape(bi_formatear(valor, formatos[i])),
                    est_celda_der if derecha[i] else est_celda,
                )
                for i, valor in enumerate(fila)
            ])

        ancho_tabla = min(ancho_total, 150 * len(encabezados))
        pesos = [
            1.8 if i == 0 and not derecha[0] else 1
            for i in range(len(encabezados))
        ]
        anchos = [ancho_tabla * peso / sum(pesos) for peso in pesos]

        objeto = Table(datos_tabla, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        objeto.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rojo),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F3F4F6")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, borde),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos += [
            Paragraph(escape(tabla["titulo"].upper()), est_seccion),
            objeto,
            Spacer(1, 3 * mm),
        ]

    marco = bi_marco_pdf(reporte["titulo"], reporte["periodo"])
    documento.build(elementos, onFirstPage=marco, onLaterPages=marco)
    return respuesta


# 10.8 Despachador de exportaciones

def bi_responder_exportacion(request, tipo, formato):
    reportes = {
        "ventas": (bi_reporte_ventas, "resumen_ventas"),
        "productos": (bi_reporte_productos, "productos_mas_vendidos"),
        "dinero": (bi_reporte_dinero, "dinero_recaudado"),
    }
    if tipo not in reportes:
        return HttpResponse("Reporte desconocido", status=404)
    if formato not in ("excel", "pdf"):
        return HttpResponse("Formato desconocido", status=404)

    if formato == "excel" and not OPENPYXL_DISPONIBLE:
        return HttpResponse(
            "Falta instalar openpyxl (pip install openpyxl).", status=503
        )
    if formato == "pdf" and not REPORTLAB_DISPONIBLE:
        return HttpResponse(
            "Falta instalar reportlab (pip install reportlab).", status=503
        )

    inicio, fin = bi_fechas(request)
    constructor, nombre = reportes[tipo]
    reporte = constructor(inicio, fin)
    archivo = f"{nombre}_{inicio:%Y%m%d}_{fin:%Y%m%d}"

    if formato == "excel":
        return bi_exportar_excel(reporte, f"{archivo}.xlsx")
    return bi_exportar_pdf(reporte, f"{archivo}.pdf")


# 10.9 Vistas web de reportes

@panel_login_requerido
@requiere_permiso('reportes.ver')
def centro_reportes(request):
    inicio, fin = bi_fechas(request)
    indicadores, _ = bi_resumen(inicio, fin)

    contexto = {
        **bi_contexto(inicio, fin),
        **indicadores,
        "indicadores": indicadores,
    }
    return render(request, "panel/reportes/centroReportes.html", contexto)


@panel_login_requerido
@requiere_permiso('reportes.ver')
def resumen_ventas(request):
    inicio, fin = bi_fechas(request)
    indicadores, ventas_diarias = bi_resumen(inicio, fin)
    metricas = bi_metricas_adicionales(inicio, fin, indicadores, ventas_diarias)

    contexto = {
        **bi_contexto(inicio, fin),
        **indicadores,
        "indicadores": indicadores,
        "ventas_diarias": ventas_diarias,
        **metricas,
    }
    return render(request, "panel/reportes/resumenVentas.html", contexto)


@panel_login_requerido
@requiere_permiso('reportes.ver')
def productos_mas_vendidos(request):
    inicio, fin = bi_fechas(request)
    productos = bi_top_productos(inicio, fin)
    total_unidades, total_ingresos = bi_totales_productos(productos)

    contexto = {
        **bi_contexto(inicio, fin),
        "productos": productos,
        "total_unidades": total_unidades,
        "total_ingresos": total_ingresos,
    }
    return render(request, "panel/reportes/productosMasVendidos.html", contexto)


@panel_login_requerido
@requiere_permiso('reportes.ver')
def dinero_recaudado(request):
    inicio, fin = bi_fechas(request)
    contexto = {**bi_contexto(inicio, fin), **bi_datos_dinero(inicio, fin)}
    return render(request, "panel/reportes/dineroRecaudado.html", contexto)


# 10.10 Vistas de exportación

@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_resumen_excel(request):
    return bi_responder_exportacion(request, "ventas", "excel")


@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_resumen_pdf(request):
    return bi_responder_exportacion(request, "ventas", "pdf")


@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_productos_excel(request):
    return bi_responder_exportacion(request, "productos", "excel")


@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_productos_pdf(request):
    return bi_responder_exportacion(request, "productos", "pdf")


@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_dinero_excel(request):
    return bi_responder_exportacion(request, "dinero", "excel")


@panel_login_requerido
@requiere_permiso('reportes.ver')
@requiere_permiso('reportes.exportar')
def exportar_dinero_pdf(request):
    return bi_responder_exportacion(request, "dinero", "pdf")
# VENTAS
 
@panel_login_requerido
def reportes(request):
    return render(request, 'panel/reportes/reportes.html')
 
 
@panel_login_requerido
def reporte_resumen_ventas(request):
    hoy = timezone.localdate()
 
    rango = request.GET.get('rango', '').strip()
    fecha_desde_txt = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_txt = request.GET.get('fecha_hasta', '').strip()
 
    atajo = _rango_por_atajo(rango, hoy)
 
    if atajo:
        desde, hasta = atajo
    else:
        rango = ''
        desde = (
            _fecha_o_none(fecha_desde_txt)
            if fecha_desde_txt else hoy - timedelta(days=6)
        )
        hasta = _fecha_o_none(fecha_hasta_txt) if fecha_hasta_txt else hoy
 
    filtros_validos = True
 
    if desde is None:
        messages.error(request, 'La fecha inicial no es válida.')
        filtros_validos = False
 
    if hasta is None:
        messages.error(request, 'La fecha final no es válida.')
        filtros_validos = False
 
    if desde and hasta:
        if desde > hasta:
            messages.error(
                request,
                'La fecha inicial no puede ser posterior a la fecha final.'
            )
            filtros_validos = False
 
        elif (hasta - desde).days + 1 > MAX_DIAS_REPORTE:
            messages.error(
                request,
                f'El período no puede superar los {MAX_DIAS_REPORTE} días.'
            )
            filtros_validos = False
 
    contexto = {
        'filtros_validos': filtros_validos,
        'rango_activo': rango,
        'fecha_desde': desde.isoformat() if desde else fecha_desde_txt,
        'fecha_hasta': hasta.isoformat() if hasta else fecha_hasta_txt,
    }
 
    if not filtros_validos:
        return render(request, 'panel/reportes/resumenVentas.html', contexto)
 
    exportar = request.GET.get('exportar') == 'xlsx'
 
    if exportar and Workbook is None:
        messages.error(request, MENSAJE_SIN_OPENPYXL)
        exportar = False
 
    datos = _datos_resumen_ventas(
        desde, hasta, limite_productos=50 if exportar else 5
    )
 
    if exportar:
        return _exportar_resumen_xlsx(datos, desde, hasta)
 
    contexto.update(datos)
    contexto['url_exportar'] = _url_exportar(request)
 
    return render(request, 'panel/reportes/resumenVentas.html', contexto)
 
 
def _pedidos_vendidos():
    return Pedido.objects.filter(pagado=True).exclude(
        idestadopedido__descripcion__iexact='Cancelado'
    )


@panel_login_requerido
def reporte_historial_ventas(request):
    """
    Historial de pedidos pagados (sin cancelados).
    Filtra por fecha inicial, fecha final y número de pedido.
    Con ?exportar=xlsx descarga todos los resultados en Excel.
    """
    pedidos = _pedidos_vendidos().select_related(
        'idcliente', 'idmediopago', 'idestadopedido'
    )
 
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    numero_pedido = request.GET.get('pedido', '').strip()
 
    desde = _fecha_o_none(fecha_desde)
    hasta = _fecha_o_none(fecha_hasta)
 
    hay_error = False
 
    if fecha_desde and desde is None:
        messages.error(request, 'La fecha inicial no es válida.')
        hay_error = True
 
    if fecha_hasta and hasta is None:
        messages.error(request, 'La fecha final no es válida.')
        hay_error = True
 
    if desde and hasta and desde > hasta:
        messages.error(
            request,
            'La fecha inicial no puede ser posterior a la fecha final.'
        )
        hay_error = True
 
    if numero_pedido and not (
        numero_pedido.isdigit() and int(numero_pedido) > 0
    ):
        messages.error(
            request, 'El número de pedido debe ser un entero positivo.'
        )
        hay_error = True
 
    if hay_error:
        pedidos = pedidos.none()
    else:
        if desde:
            pedidos = pedidos.filter(fecha_creacion__date__gte=desde)
 
        if hasta:
            pedidos = pedidos.filter(fecha_creacion__date__lte=hasta)
 
        if numero_pedido:
            pedidos = pedidos.filter(idpedido=int(numero_pedido))
 
    pedidos = pedidos.order_by('-fecha_creacion', '-idpedido')
 
    if request.GET.get('exportar') == 'xlsx' and not hay_error:
        if Workbook is None:
            messages.error(request, MENSAJE_SIN_OPENPYXL)
        else:
            partes = []
 
            if desde:
                partes.append(f'desde {desde:%d/%m/%Y}')
 
            if hasta:
                partes.append(f'hasta {hasta:%d/%m/%Y}')
 
            if numero_pedido:
                partes.append(f'pedido #{numero_pedido}')
 
            return _exportar_historial_xlsx(
                pedidos,
                'Filtros: ' + (' · '.join(partes) or 'todos los pedidos'),
            )
 
    resumen = pedidos.aggregate(
        total_ventas=Sum('total'),
        cantidad_pedidos=Count('idpedido'),
        ticket_promedio=Avg('total'),
    )
 
    pagina = Paginator(pedidos, 15).get_page(request.GET.get('pagina'))
 
    return render(request, 'panel/reportes/historialVentas.html', {
        'pagina_pedidos': pagina,
        'total_ventas': resumen['total_ventas'] or CERO,
        'cantidad_pedidos': resumen['cantidad_pedidos'] or 0,
        'ticket_promedio': resumen['ticket_promedio'] or CERO,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'numero_pedido': numero_pedido,
        'url_exportar': _url_exportar(request),
    })
# HORARIOS
class HorarioForm(forms.ModelForm):
    DIAS_SEMANA = [
        ("Lunes", "Lunes"),
        ("Martes", "Martes"),
        ("Miércoles", "Miércoles"),
        ("Jueves", "Jueves"),
        ("Viernes", "Viernes"),
        ("Sábado", "Sábado"),
        ("Domingo", "Domingo"),
    ]

    ESTADOS = [
        (1, "Abierto"),
        (0, "Cerrado"),
    ]

    diasemana = forms.ChoiceField(
        choices=DIAS_SEMANA,
        label="Día de la semana",
        widget=forms.Select(attrs={"class": "form-control"})
    )

    idnegocio = forms.ModelChoiceField(
        queryset=Negocio.objects.all(),
        label="Negocio",
        empty_label="Seleccioná un negocio",
        widget=forms.Select(attrs={"class": "form-control"})
    )

    horaapertura = forms.TimeField(
        label="Hora de apertura",
        required=False,
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={"type": "time", "class": "form-control"}
        )
    )

    horacierre = forms.TimeField(
        label="Hora de cierre",
        required=False,
        input_formats=["%H:%M"],
        widget=forms.TimeInput(
            format="%H:%M",
            attrs={"type": "time", "class": "form-control"}
        )
    )

    estaabierto = forms.TypedChoiceField(
        choices=ESTADOS,
        label="Estado del día",
        coerce=int,
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Horario
        fields = [
            "idnegocio",
            "diasemana",
            "horaapertura",
            "horacierre",
            "estaabierto",
        ]

    def clean(self):
        cleaned_data = super().clean()
        estaabierto = cleaned_data.get("estaabierto")
        apertura = cleaned_data.get("horaapertura")
        cierre = cleaned_data.get("horacierre")

        if estaabierto == 1:
            if not apertura or not cierre:
                raise forms.ValidationError(
                    "Si el día está configurado como abierto, debés indicar la hora de apertura y de cierre."
                )

            if apertura != cierre:  # Misma hora significa 24 horas continuas
                ap_min = apertura.hour * 60 + apertura.minute
                ci_min = cierre.hour * 60 + cierre.minute
                duracion = ci_min - ap_min

                if duracion < 30:
                    raise forms.ValidationError(
                        "El horario de atención configurado debe tener una duración mínima de al menos 30 minutos."
                    )

        # No se permiten franjas solapadas ni un día cerrado y abierto a la vez.
        negocio = cleaned_data.get("idnegocio")
        dia = cleaned_data.get("diasemana")

        if negocio and dia and estaabierto is not None:
            otros = Horario.objects.filter(idnegocio=negocio, diasemana=dia)
            if self.instance and self.instance.pk:
                otros = otros.exclude(pk=self.instance.pk)

            def _franja(inicio, fin):
                ini = inicio.hour * 60 + inicio.minute
                fi = fin.hour * 60 + fin.minute
                if fi == ini:
                    return ini, ini + 1440
                return (ini, fi + 1440) if fi < ini else (ini, fi)

            for otro in otros:
                otro_abierto = otro.estaabierto == 1

                if (estaabierto == 1) != otro_abierto:
                    raise forms.ValidationError(
                        f"El día {dia} ya tiene un horario cargado como "
                        f"{'abierto' if otro_abierto else 'cerrado'}: "
                        "no puede estar abierto y cerrado a la vez."
                    )

                if (
                    estaabierto == 1 and otro_abierto
                    and apertura and cierre
                    and otro.horaapertura and otro.horacierre
                ):
                    ini_a, fin_a = _franja(apertura, cierre)
                    ini_b, fin_b = _franja(otro.horaapertura, otro.horacierre)
                    if ini_a < fin_b and ini_b < fin_a:
                        raise forms.ValidationError(
                            f"La franja se superpone con otra ya cargada para {dia} "
                            f"({otro.horaapertura:%H:%M} a {otro.horacierre:%H:%M})."
                        )

        return cleaned_data

@panel_login_requerido
@requiere_permiso('horarios.ver')
def horarios_lista(request):
    horarios = Horario.objects.select_related("idnegocio").order_by(
        "idnegocio__nombre", "idhorario"
    )
    return render(
        request,
        "panel/horarios/horarioLista.html",
        {"horarios": horarios},
    )


@panel_login_requerido
@requiere_permiso('horarios.crear')
def horarios_crear(request):
    if request.method == "POST":
        form = HorarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Horario creado correctamente.")
            return redirect("horarios_lista")
    else:
        form = HorarioForm()

    return render(request, "panel/horarios/horarioCrear.html", {
        "form": form,
        "titulo": "Crear horario",
        "accion": "Crear horario",
    })


@panel_login_requerido
@requiere_permiso('horarios.editar')
def horarios_editar(request, idhorario):
    horario = get_object_or_404(Horario, pk=idhorario)

    if request.method == "POST":
        form = HorarioForm(request.POST, instance=horario)
        if form.is_valid():
            form.save()
            messages.success(request, "Horario actualizado correctamente.")
            return redirect("horarios_lista")
    else:
        form = HorarioForm(instance=horario)

    return render(request, "panel/horarios/horarioEditar.html", {
        "form": form,
        "titulo": "Editar horario",
        "accion": "Guardar cambios",
    })


@panel_login_requerido
@requiere_permiso('horarios.eliminar')
def horarios_eliminar(request, idhorario):
    horario = get_object_or_404(Horario, pk=idhorario)

    if request.method == "POST":
        horario.delete()
        messages.success(request, "Horario eliminado correctamente.")
        return redirect("horarios_lista")

    return render(
        request,
        "panel/horarios/horarioEliminar.html",
        {"horario": horario},
    )
# ZONAS ENTREGA
@panel_login_requerido
@requiere_permiso('zonas.ver')
def zonas_entrega_lista(request):
    zonas = ZonasEntrega.objects.all().order_by("nombre", "idzona")

    return render(
        request,
        "panel/entrega/zonaLista.html",
        {"zonas": zonas},
    )


@panel_login_requerido
@requiere_permiso('zonas.crear')
def zonas_entrega_crear(request):
    negocios = Negocio.objects.all().order_by("idnegocio")

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        costo_raw = request.POST.get("costoenvio", "").strip()
        idnegocio_raw = request.POST.get("idnegocio", "").strip()

        contexto = {
            "negocios": negocios,
            "nombre_ingresado": nombre,
            "costo_ingresado": costo_raw,
            "negocio_seleccionado": idnegocio_raw,
        }

        try:
            if not nombre:
                raise ValueError("El nombre de la zona es obligatorio.")

            if len(nombre) > 50:
                raise ValueError(
                    "El nombre no puede superar los 50 caracteres."
                )

            costoenvio = Decimal(
                costo_raw.replace(",", ".") if costo_raw else "0"
            )

            if not costoenvio.is_finite() or costoenvio < 0:
                raise ValueError(
                    "El costo de envío debe ser válido y no negativo."
                )

            if costoenvio.as_tuple().exponent < -2:
                raise ValueError(
                    "El costo admite como máximo dos decimales."
                )

            if costoenvio >= Decimal("100000000"):
                raise ValueError("El costo de envío es demasiado alto.")

            if not idnegocio_raw:
                raise ValueError("Seleccioná una sucursal.")

            idnegocio = int(idnegocio_raw)

            if not negocios.filter(pk=idnegocio).exists():
                raise ValueError("La sucursal seleccionada no es válida.")

            if ZonasEntrega.objects.filter(
                nombre__iexact=nombre, idnegocio=idnegocio
            ).exists():
                raise ValueError("Ya existe una zona de entrega con ese nombre.")

            ZonasEntrega.objects.create(
                nombre=nombre,
                costoenvio=costoenvio,
                idnegocio=idnegocio,
            )

            messages.success(
                request,
                "Zona de entrega creada correctamente."
            )
            return redirect("zonas_entrega_lista")

        except (ValueError, InvalidOperation, TypeError) as e:
            messages.error(request, str(e))
        except DatabaseError as e:
            print(f"Error al crear zona de entrega: {e}")
            messages.error(
                request,
                "No se pudo guardar la zona. Revisá el error en la consola."
            )

        return render(
            request,
            "panel/entrega/zonaCrear.html",
            contexto,
        )

    return render(
        request,
        "panel/entrega/zonaCrear.html",
        {"negocios": negocios},
    )


@panel_login_requerido
@requiere_permiso('zonas.editar')
def zonas_entrega_editar(request, idzona):
    zona = get_object_or_404(ZonasEntrega, pk=idzona)

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        costo_raw = request.POST.get("costoenvio", "0").strip()

        if nombre and ZonasEntrega.objects.filter(
            nombre__iexact=nombre, idnegocio=zona.idnegocio
        ).exclude(pk=zona.pk).exists():
            messages.error(request, "Ya existe otra zona de entrega con ese nombre.")
            return render(
                request,
                "panel/entrega/zonaEditar.html",
                {"zona": zona},
            )

        try:
            if not nombre:
                raise ValueError("El nombre es obligatorio.")

            if len(nombre) > 50:
                raise ValueError("El nombre no puede superar los 50 caracteres.")

            costoenvio = Decimal(costo_raw or "0")

            if not costoenvio.is_finite() or costoenvio < 0:
                raise ValueError("El costo debe ser un número válido mayor o igual a cero.")

            zona.nombre = nombre
            zona.costoenvio = costoenvio
            zona.save(update_fields=["nombre", "costoenvio"])

            messages.success(
                request,
                "Zona de entrega actualizada correctamente.",
            )
            return redirect("zonas_entrega_lista")

        except (ValueError, InvalidOperation, TypeError):
            messages.error(
                request,
                "Verificá el nombre y el costo de envío. El costo debe ser válido y no negativo.",
            )

    return render(
        request,
        "panel/entrega/zonaEditar.html",
        {"zona": zona},
    )


@panel_login_requerido
@requiere_permiso('zonas.eliminar')
def zonas_entrega_eliminar(request, idzona):
    zona = get_object_or_404(ZonasEntrega, pk=idzona)

    if request.method == "POST":
        zona.delete()
        messages.success(request, "Zona de entrega eliminada correctamente.")
        return redirect("zonas_entrega_lista")

    return render(
        request,
        "panel/entrega/zonaEliminar.html",
        {"zona": zona},
    )
# historial de pedidos
def _fecha_o_none(texto):
    """Devuelve la fecha o None si el texto no es una fecha válida."""
    try:
        return parse_date(texto) if texto else None
    except ValueError:
        return None
    
@panel_login_requerido
@requiere_permiso('historial.ver')
def historial_pedidos(request):
    """Historial general de pedidos, independientemente de su estado."""
    pedidos = Pedido.objects.select_related(
        'idcliente',
        'idmediopago',
        'idestadopedido',
    ).all()

    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    numero_pedido = request.GET.get('pedido', '').strip()
    cliente = request.GET.get('cliente', '').strip()
    estado = request.GET.get('estado', '').strip()

    desde = _fecha_o_none(fecha_desde) if fecha_desde else None
    hasta = _fecha_o_none(fecha_hasta) if fecha_hasta else None
    hay_error = False

    if fecha_desde and desde is None:
        messages.error(request, 'La fecha inicial no es válida.')
        hay_error = True

    if fecha_hasta and hasta is None:
        messages.error(request, 'La fecha final no es válida.')
        hay_error = True

    if desde and hasta and desde > hasta:
        messages.error(
            request,
            'La fecha inicial no puede ser posterior a la fecha final.'
        )
        hay_error = True

    if numero_pedido and not (
        numero_pedido.isdigit() and int(numero_pedido) > 0
    ):
        messages.error(
            request,
            'El número de pedido debe ser un entero positivo.'
        )
        hay_error = True

    if estado and not estado.isdigit():
        messages.error(request, 'El estado seleccionado no es válido.')
        hay_error = True

    if hay_error:
        pedidos = pedidos.none()
    else:
        if desde:
            pedidos = pedidos.filter(fecha_creacion__date__gte=desde)

        if hasta:
            pedidos = pedidos.filter(fecha_creacion__date__lte=hasta)

        if numero_pedido:
            pedidos = pedidos.filter(idpedido=int(numero_pedido))

        if cliente:
            pedidos = pedidos.filter(
                Q(idcliente__nombre__icontains=cliente)
                | Q(idcliente__apellido__icontains=cliente)
            )

        if estado:
            pedidos = pedidos.filter(idestadopedido__idestado=int(estado))

    pedidos = pedidos.order_by('-idpedido')
    estados = EstadoPedido.objects.all().order_by('descripcion')

    pagina = Paginator(pedidos, 15).get_page(
        request.GET.get('pagina')
    )

    return render(request, 'panel/ventas/historialPedidos.html', {
        'pagina_pedidos': pagina,
        'estados': estados,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'numero_pedido': numero_pedido,
        'cliente': cliente,
        'estado_seleccionado': estado,
    })


@panel_login_requerido
@requiere_permiso('historial.ver')
def detalle_historial_pedido(request, idpedido):
    """Detalle completo de un pedido del historial."""
    pedido = Pedido.objects.select_related(
        'idcliente',
        'idmediopago',
        'idestadopedido',
    ).filter(idpedido=idpedido).first()

    if pedido is None:
        # 404 con página amigable (también con DEBUG=True).
        return render(
            request,
            'panel/ventas/pedidoNoEncontrado.html',
            {'idpedido': idpedido},
            status=404,
        )

    detalles = DetallePedido.objects.filter(
        idpedido=pedido
    ).select_related('idproducto')

    for detalle in detalles:
        detalle.subtotal_item = detalle.preciounitario * detalle.cantidad

    return render(request, 'panel/ventas/detalleHistorialPedido.html', {
        'pedido': pedido,
        'detalles': detalles,
    })
# 11. PANEL - ABRIR / CERRAR EL NEGOCIO

# 11.1 Constantes

# Estados fijos de EstadoNegocio (se crean solos la primera vez que se usan)
LOCAL_AUTOMATICO = "Automático"
LOCAL_ABIERTO_MANUAL = "Abierto manual"
LOCAL_CERRADO_MANUAL = "Cerrado manual"

# Prefijo con el que se registran los cambios en UltimaModificacion
LOCAL_PREFIJO_LOG = "Estado del local:"

# Si no hay horarios cargados, ¿se considera abierto?
# True evita bloquear pedidos mientras no se carguen los horarios.
LOCAL_SIN_HORARIOS_ABIERTO = True

LOCAL_DIAS = [
    "lunes", "martes", "miercoles", "jueves",
    "viernes", "sabado", "domingo",
]
LOCAL_DIAS_TXT = [
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
]

LOCAL_TEXTO_LOG = {
    LOCAL_AUTOMATICO: "volvió al modo automático (según horarios)",
    LOCAL_ABIERTO_MANUAL: "abierto manualmente por hoy",
    LOCAL_CERRADO_MANUAL: "cerrado manualmente por hoy",
}


# 11.2 Utilidades

def local_normalizar(texto):
    texto = unicodedata.normalize("NFD", texto or "")
    sin_tildes = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return sin_tildes.strip().lower()


LOCAL_INDICE_DIA = {nombre: i for i, nombre in enumerate(LOCAL_DIAS)}
LOCAL_MODOS = {
    local_normalizar(modo): modo
    for modo in (LOCAL_AUTOMATICO, LOCAL_ABIERTO_MANUAL, LOCAL_CERRADO_MANUAL)
}


def local_ahora():
    ahora = timezone.now()
    return timezone.localtime(ahora) if timezone.is_aware(ahora) else ahora


def local_a_local(momento):
    return timezone.localtime(momento) if timezone.is_aware(momento) else momento


def local_nombre_empleado(empleado):
    if empleado is None:
        return ""
    return f"{empleado.nombre} {getattr(empleado, 'apellido', '')}".strip()


# 11.3 Horarios automáticos

def local_franjas(horarios):
    """[(día 0-6, apertura, cierre)] solo de los días marcados como abiertos."""
    franjas = []
    for h in horarios:
        if not (h.estaabierto and h.horaapertura and h.horacierre):
            continue
        dia = LOCAL_INDICE_DIA.get(local_normalizar(h.diasemana))
        if dia is not None:
            franjas.append((dia, h.horaapertura, h.horacierre))
    return franjas


def local_abierto_por_horario(franjas, ahora):
    dia, hora = ahora.weekday(), ahora.time()
    for d, apertura, cierre in franjas:
        if apertura == cierre:                       # 24 horas
            if d == dia:
                return True
        elif apertura < cierre:                      # mismo día
            if d == dia and apertura <= hora < cierre:
                return True
        else:                                        # cruza la medianoche
            if d == dia and hora >= apertura:
                return True
            if d == (dia - 1) % 7 and hora < cierre:
                return True
    return False


def local_proxima_apertura(franjas, desde):
    candidatas = []
    for desplazamiento in range(8):
        fecha = desde.date() + timedelta(days=desplazamiento)
        for d, apertura, _ in franjas:
            if d == fecha.weekday():
                momento = datetime.combine(fecha, apertura, tzinfo=desde.tzinfo)
                if momento > desde:
                    candidatas.append(momento)
    return min(candidatas) if candidatas else None


def local_texto_apertura(momento, ahora):
    dias = (momento.date() - ahora.date()).days
    if dias == 0:
        cuando = "hoy"
    elif dias == 1:
        cuando = "mañana"
    else:
        cuando = f"el {LOCAL_DIAS_TXT[momento.weekday()]}"
    return f"{cuando} a las {momento:%H:%M}"


# 11.4 Estado actual del local

def local_estado_por_defecto():
    return {
        "abierto": True,
        "manual": False,
        "mensaje": "",
        "ultimo_cambio": None,
        "ultimo_por": "",
    }


def local_estado():
    """
    Estado actual del local (se usa en el panel y, más adelante,
    para bloquear carrito y checkout). Devuelve un diccionario:
    abierto, manual (hay un cierre/apertura manual vigente HOY),
    mensaje, ultimo_cambio y ultimo_por.
    """
    try:
        return local_calcular_estado()
    except Exception:
        logger.exception("No se pudo calcular el estado del local")
        return local_estado_por_defecto()


def local_calcular_estado():
    ahora = local_ahora()
    negocio = Negocio.objects.select_related("idestado").first()

    if negocio is None:
        return local_estado_por_defecto()

    registro = (
        UltimaModificacion.objects
        .select_related("idempleado")
        .filter(
            idnegocio=negocio.idnegocio,
            descripcioncambio__startswith=LOCAL_PREFIJO_LOG,
        )
        .order_by("-fecha")
        .first()
    )

    descripcion = (
        negocio.idestado.descripcion
        if negocio.idestado_id
        else ""
    )
    modo = LOCAL_MODOS.get(
        local_normalizar(descripcion),
        LOCAL_AUTOMATICO,
    )

    # El modo manual solo tiene validez durante el día en que
    # se registró la última apertura o cierre manual.
    manual_vigente = (
        modo != LOCAL_AUTOMATICO
        and registro is not None
        and local_a_local(registro.fecha).date() == ahora.date()
    )

    franjas = local_franjas(
        Horario.objects.filter(idnegocio=negocio)
    )

    if manual_vigente:
        abierto = modo == LOCAL_ABIERTO_MANUAL

    elif franjas:
        # Si el cambio manual es de otro día, volver al horario.
        abierto = local_abierto_por_horario(franjas, ahora)

    else:
        # Mantener el comportamiento configurado si no hay horarios.
        abierto = LOCAL_SIN_HORARIOS_ABIERTO

    if abierto:
        mensaje = "Estamos abiertos."

    else:
        if manual_vigente:
            # Si se cerró manualmente, buscar la próxima apertura
            # a partir del final del día actual.
            medianoche = datetime.combine(
                ahora.date() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=ahora.tzinfo,
            )

            proxima = local_proxima_apertura(
                franjas,
                medianoche - timedelta(seconds=1),
            )

            mensaje = "Hoy el local permanece cerrado."

        else:
            proxima = local_proxima_apertura(franjas, ahora)
            mensaje = "En este momento estamos cerrados."

        if proxima:
            mensaje += (
                f" Volvemos a abrir "
                f"{local_texto_apertura(proxima, ahora)}."
            )

    return {
        "abierto": abierto,
        "manual": manual_vigente,
        "mensaje": mensaje,
        "ultimo_cambio": (
            local_a_local(registro.fecha)
            if registro else None
        ),
        "ultimo_por": (
            local_nombre_empleado(registro.idempleado)
            if registro else ""
        ),
    }

# Entrega programada
ENTREGA_MARGEN_CIERRE_MIN = 30   # última entrega: 30 min antes de cerrar
ENTREGA_ANTICIPACION_MIN = 20    # mínimo: dentro de 20 min a partir de ahora


def _min_a_hhmm(minutos):
    minutos %= 1440
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def local_ventanas_entrega(estado=None):
    """
    Franjas en las que se puede pedir un horario de entrega, en minutos desde
    las 00:00 de hoy (pueden pasar de 1440 si cruzan la medianoche).
    """
    libre = {
        'restringido': False,
        'ventanas': [],
        'texto': '',
        'margen': ENTREGA_MARGEN_CIERRE_MIN,
    }

    try:
        negocio = Negocio.objects.first()
        if negocio is None:
            return libre

        franjas = local_franjas(Horario.objects.filter(idnegocio=negocio))
        if not franjas:
            return libre

        ahora = local_ahora()
        ahora_min = ahora.hour * 60 + ahora.minute + (1 if ahora.second else 0)
        hoy = ahora.weekday()
        ayer = (hoy - 1) % 7

        brutas = []
        for d, apertura, cierre in franjas:
            ap = apertura.hour * 60 + apertura.minute
            ci = cierre.hour * 60 + cierre.minute
            if ap == ci:                       # 24 horas
                if d == hoy:
                    brutas.append((0, 1440))
            elif ap < ci:                      # mismo día
                if d == hoy:
                    brutas.append((ap, ci))
            else:                              # cruza la medianoche
                if d == hoy:
                    brutas.append((ap, ci + 1440))
                if d == ayer:
                    brutas.append((ap - 1440, ci))

        estado = estado if estado is not None else local_estado()

        # Abierto a mano fuera de horario: no hay cierre conocido.
        if (
            estado.get('abierto') and estado.get('manual')
            and not any(i <= ahora_min < f for i, f in brutas)
        ):
            return libre

        ventanas = []
        for inicio, fin in sorted(brutas):
            desde = max(inicio, ahora_min + ENTREGA_ANTICIPACION_MIN)
            hasta = fin - ENTREGA_MARGEN_CIERRE_MIN
            if hasta >= desde:
                ventanas.append({'desde': desde, 'hasta': hasta})

        texto = ' y '.join(
            f"{_min_a_hhmm(v['desde'])} a {_min_a_hhmm(v['hasta'])}"
            for v in ventanas
        )

        return {
            'restringido': True,
            'ventanas': ventanas,
            'texto': texto,
            'margen': ENTREGA_MARGEN_CIERRE_MIN,
        }

    except Exception:
        logger.exception("No se pudieron calcular los horarios de entrega")
        return libre


def error_horario_entrega(hora, info=None):
    """Devuelve el mensaje de error o '' si el horario es válido."""
    info = info or local_ventanas_entrega()

    if not info['restringido']:
        return ''

    minutos = hora.hour * 60 + hora.minute

    for v in info['ventanas']:
        if (
            v['desde'] <= minutos <= v['hasta']
            or v['desde'] <= minutos + 1440 <= v['hasta']
        ):
            return ''

    if info['ventanas']:
        return (
            f"Elegí un horario dentro de: {info['texto']} hs. "
            f"Dejamos {info['margen']} minutos antes del cierre para llegar a tiempo."
        )

    return (
        'Hoy ya no hay horarios de entrega disponibles. '
        'Dejá el horario vacío para coordinarlo con el local.'
    )

# 11.5 Cambio de modo (abrir / cerrar / automático)

def local_estado_fijo(descripcion):
    return EstadoNegocio.objects.filter(descripcion=descripcion).first()


def local_aplicar_modo(modo, empleado=None):
    """Guarda el nuevo modo y deja registro de quién y cuándo. Devuelve el Negocio."""
    with transaction.atomic():
        negocio = Negocio.objects.select_for_update().first()
        if negocio is None:
            return None

        ahora = local_ahora()
        estado = local_estado_fijo(modo)
        if estado is None:
            raise ValueError(f"Falta cargar en EstadoNegocio el estado '{modo}'.")

        UltimaModificacion.objects.create(
            fecha=ahora,
            idempleado=empleado,
            descripcioncambio=f"{LOCAL_PREFIJO_LOG} {LOCAL_TEXTO_LOG[modo]}",
            idnegocio=negocio.idnegocio,
            idestado=estado,
        )

        negocio.idestado = estado
        negocio.idempleado = empleado
        negocio.save(update_fields=["idestado", "idempleado"])
    return negocio


# 11.6 Vistas del panel

@panel_login_requerido
@requiere_permiso('negocio.ver')
def estado_negocio_panel(request):
    estado = local_estado()
    negocio = Negocio.objects.first()

    cambios = []
    total_aperturas = total_cierres = total_automatico = 0

    if negocio:
        base = UltimaModificacion.objects.filter(
            idnegocio=negocio.idnegocio,
            descripcioncambio__startswith=LOCAL_PREFIJO_LOG,
        )

        def contar(modo):
            return base.filter(
                descripcioncambio=f"{LOCAL_PREFIJO_LOG} {LOCAL_TEXTO_LOG[modo]}"
            ).count()

        total_aperturas = contar(LOCAL_ABIERTO_MANUAL)
        total_cierres = contar(LOCAL_CERRADO_MANUAL)
        total_automatico = contar(LOCAL_AUTOMATICO)

        modos_por_texto = {texto: modo for modo, texto in LOCAL_TEXTO_LOG.items()}
        acciones = {
            LOCAL_ABIERTO_MANUAL: ("Abrió el local", "abrio"),
            LOCAL_CERRADO_MANUAL: ("Cerró el local", "cerro"),
            LOCAL_AUTOMATICO: ("Volvió a modo automático", "auto"),
        }

        registros = (
            base.select_related("idempleado")
            .order_by("-fecha")[:100]
        )

        for posicion, registro in enumerate(registros):
            texto = (registro.descripcioncambio or "")[len(LOCAL_PREFIJO_LOG):].strip()
            modo = modos_por_texto.get(texto)
            accion, clase = acciones.get(modo, (texto or "Cambio", "auto"))

            cambios.append({
                "fecha": local_a_local(registro.fecha),
                "accion": accion,
                "clase": clase,
                "quien": (
                    local_nombre_empleado(registro.idempleado)
                    or "Sin usuario registrado"
                ),
                "vigente": posicion == 0 and estado["manual"],
            })

    contexto = {
        "estado_local": estado,
        "cambios": cambios,
        "total_aperturas": total_aperturas,
        "total_cierres": total_cierres,
        "total_automatico": total_automatico,
    }
    return render(request, "panel/negocio/interruptorNegocio.html", contexto)


LOCAL_PERMISO_POR_ACCION = {
    'abrir': 'negocio.abrir',
    'cerrar': 'negocio.cerrar',
    'automatico': 'negocio.automatico',
}
for _permiso in LOCAL_PERMISO_POR_ACCION.values():
    registrar_permiso(_permiso)


@panel_login_requerido
@require_POST
def cambiar_estado_local(request):
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destino = "/"

    modos = {
        "abrir": (
            LOCAL_ABIERTO_MANUAL,
            "El local quedó abierto por hoy. Mañana vuelve a regirse por los horarios.",
        ),
        "cerrar": (
            LOCAL_CERRADO_MANUAL,
            "El local quedó cerrado por hoy. Mañana abre normalmente según los horarios.",
        ),
        "automatico": (
            LOCAL_AUTOMATICO,
            "El local volvió al modo automático según los horarios.",
        ),
    }

    accion = request.POST.get("accion")
    if accion not in modos:
        messages.error(request, "Acción no válida.")
        return redirect(destino)

    permiso_req = LOCAL_PERMISO_POR_ACCION.get(accion)
    if permiso_req and hasattr(request.user, 'tiene_permiso') and not request.user.tiene_permiso(permiso_req):
        messages.error(request, 'No tenés permiso para modificar el estado del local.')
        return redirect(destino)

    modo, texto = modos[accion]
    empleado = request.user if isinstance(request.user, Empleado) else None
    negocio = local_aplicar_modo(modo, empleado)

    if negocio is None:
        messages.error(request, "No hay un negocio configurado.")
    else:
        registrar_auditoria(request, f'NEGOCIO_{accion.upper()}', f'Estado del negocio cambiado a {modo}')
        messages.success(request, texto)

    return redirect(destino)


# 12. API DE ESTADO EN TIEMPO REAL

def _payload_carrito(request):
    carrito = request.session.get('carrito', {})
    carrito, quitados = _depurar_carrito(request, carrito)
    estado = local_estado()

    items = []
    for item_id, it in carrito.items():
        items.append({
            'id': str(item_id),
            'nombre': it.get('nombre', ''),
            'detalles': list(it.get('detalles') or []),
            'cantidad': it.get('cantidad', 1),
            'precio_unitario': float(it.get('precio_unitario', 0)),
            'subtotal': float(it.get('subtotal', 0)),
            'url_editar': reverse('editar_item_carrito', args=[item_id]),
        })

    payload = {
        'abierto': bool(estado.get('abierto', True)),
        'mensaje': estado.get('mensaje', ''),
        'items': items,
        'total': round(sum(i['subtotal'] for i in items), 2),
    }
    payload['version'] = hashlib.sha1(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    payload['quitados'] = quitados  # evento, fuera del hash
    return payload


def api_carrito_estado(request):
    return _json_sin_cache(_payload_carrito(request))


@require_POST
def api_carrito_accion(request):
    item_id = request.POST.get('item_id', '')
    accion = request.POST.get('accion', '')
    carrito = request.session.get('carrito', {})
    error = ''

    if item_id in carrito:
        item = carrito[item_id]
        if accion == 'aumentar':
            if not local_estado().get('abierto', True):
                error = ('En este momento el negocio está cerrado. '
                         'No es posible agregar productos al carrito.')
            else:
                item['cantidad'] = int(item.get('cantidad', 1)) + 1
        elif accion == 'disminuir':
            item['cantidad'] = int(item.get('cantidad', 1)) - 1
            if item['cantidad'] <= 0:
                del carrito[item_id]
        elif accion == 'eliminar':
            del carrito[item_id]

        if item_id in carrito:
            carrito[item_id]['subtotal'] = float(_precio_dos_decimales(
                _decimal_seguro(carrito[item_id]['precio_unitario'])
                * carrito[item_id]['cantidad']
            ))

        if not carrito:
            for k in ('promocion_id', 'codigo_promocion', 'descuento_promocion'):
                request.session.pop(k, None)

        request.session['carrito'] = carrito
        request.session.modified = True

    payload = _payload_carrito(request)
    if error:
        payload['error'] = error
    return _json_sin_cache(payload, status=400 if error else 200)

def api_estado_negocio(request):
    """
    Devuelve el estado del local, las promociones activas,
    los horarios y las zonas de entrega en formato JSON.
    """
    negocio = Negocio.objects.first()
    hoy = timezone.localdate()

    # Estado actual del negocio
    estado = local_estado()

    if isinstance(estado, dict):
        abierto = bool(estado.get("abierto", False))
        mensaje = estado.get("mensaje", "")
    else:
        abierto = bool(getattr(estado, "abierto", False))
        mensaje = getattr(estado, "mensaje", "")

    # Promociones vigentes
    promociones_qs = Promocion.objects.filter(
        activo=1
    ).filter(
        Q(fechainicio__isnull=True) | Q(fechainicio__lte=hoy)
    ).filter(
        Q(fechafin__isnull=True) | Q(fechafin__gte=hoy)
    )

    promociones = []

    for promo in promociones_qs:
        productos = []

        for relacion in promo.productopromocion_set.select_related(
            "idproducto"
        ).all():
            producto = relacion.idproducto

            if producto:
                productos.append({
                    "nombre": producto.nombre
                })

        promociones.append({
            "id": promo.pk,
            "palabraclave": promo.palabraclave or "",
            "descripcion_amigable": (
                promo.descripcion_amigable or ""
            ),
            "fechafin": (
                promo.fechafin.isoformat()
                if promo.fechafin else None
            ),
            "productos": productos
        })

    # Horarios del negocio
    if negocio:
        horarios_qs = Horario.objects.filter(
            idnegocio=negocio
        )
    else:
        horarios_qs = Horario.objects.none()

    horarios = []

    for horario in horarios_qs:
        horarios.append({
            "diasemana": str(horario.diasemana or ""),
            "horaapertura": (
                horario.horaapertura.strftime("%H:%M")
                if horario.horaapertura else ""
            ),
            "horacierre": (
                horario.horacierre.strftime("%H:%M")
                if horario.horacierre else ""
            )
        })

    # Zonas de entrega
    if negocio:
        zonas_qs = ZonasEntrega.objects.filter(
            idnegocio=negocio.idnegocio
        )
    else:
        zonas_qs = ZonasEntrega.objects.none()

    zonas = []

    for zona in zonas_qs:
        zonas.append({
            "nombre": str(zona.nombre or ""),
            "costoenvio": zona.costoenvio
        })

    return JsonResponse({
        "abierto": abierto,
        "mensaje": mensaje,
        "promociones": promociones,
        "horarios": horarios,
        "zonas": zonas
    })



def api_detectar_zona(request):
    """
    API en tiempo real para detectar la zona de entrega y calcular automáticamente el costo de envío
    según la dirección real y ubicación geográfica del cliente.
    """
    calle = request.GET.get('calle') or request.POST.get('calle') or ''
    numero = request.GET.get('numero') or request.POST.get('numero') or ''
    localidad = request.GET.get('localidad') or request.POST.get('localidad') or ''
    lat = request.GET.get('lat') or request.POST.get('lat')
    lon = request.GET.get('lon') or request.POST.get('lon')
    id_zona = request.GET.get('id_zona') or request.POST.get('id_zona')

    from core.geo_zonas import detectar_zona_entrega

    resultado = detectar_zona_entrega(
        calle=calle,
        numero=numero,
        localidad=localidad,
        lat=lat,
        lon=lon,
        id_zona_sugerida=id_zona if (id_zona and id_zona != 'otro') else None,
    )

    zona_obj = resultado.get('zona')
    zona_data = None
    if zona_obj:
        zona_data = {
            'idzona': zona_obj.idzona,
            'nombre': zona_obj.nombre,
            'costoenvio': str(resultado.get('costoenvio')),
            'es_gratis': resultado.get('es_gratis', False),
        }

    return JsonResponse({
        'status': 'success',
        'cobertura': resultado.get('cobertura', False),
        'es_a_coordinar': resultado.get('es_a_coordinar', True),
        'zona': zona_data,
        'idzona': resultado.get('idzona'),
        'nombre_zona': resultado.get('nombre'),
        'costo_envio': float(resultado.get('costoenvio', 0)),
        'es_gratis': resultado.get('es_gratis', False),
        'costo_envio_texto': resultado.get('costoenvio_texto'),
        'localidad_guardar': resultado.get('localidad_guardar'),
        'mensaje': resultado.get('mensaje'),
        'metodo_deteccion': resultado.get('metodo_deteccion'),
    })


# 13. PANEL - AUTENTICACIÓN, PERFIL Y SEGURIDAD

def panel_login(request):

    # Si ya inició sesión, comprobar que la cuenta siga activa.
    if getattr(request.user, 'is_authenticated', False):
        empleado_actual = Empleado.objects.filter(
            pk=request.user.pk
        ).first()

        cuenta_activa = (
            empleado_actual is not None
            and empleado_actual.activo
            and getattr(request.user, 'is_active', True)
        )

        if cuenta_activa:
            return redirect('panel_inicio')

        # Cerrar la sesión si la cuenta fue desactivada.
        logout(request)
        messages.error(
            request,
            'Tu cuenta está desactivada. Por favor contactá al administrador.'
        )

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        ip_cliente = obtener_ip_cliente(request)

        next_url = (
            request.POST.get('next')
            or request.GET.get('next')
            or reverse('panel_inicio')
        )

        if not username or not password:
            messages.error(
                request,
                'Por favor ingresá tu usuario/correo y contraseña.'
            )
            return render(request, 'panel/login.html')

        # Control de seguridad: Verificar bloqueo por intentos fallidos excesivos (fuerza bruta)
        esta_bloqueado, tiempo_bloqueo = verificar_bloqueo_fuerza_bruta(username, ip_cliente)
        if esta_bloqueado:
            messages.error(
                request,
                'Demasiados intentos fallidos de inicio de sesión. '
                'Por motivos de seguridad, el acceso ha sido bloqueado temporalmente. '
                'Por favor, esperá unos minutos e intentá nuevamente.'
            )
            return render(request, 'panel/login.html')

        empleado = (
            Empleado.objects.filter(correo__iexact=username).first()
            or Empleado.objects.filter(nombre__iexact=username).first()
        )

        # Bloquear explícitamente las cuentas desactivadas antes de autenticar.
        if empleado and not empleado.activo:
            messages.error(
                request,
                'Tu cuenta está desactivada. Por favor contactá al administrador.'
            )
            return render(request, 'panel/login.html')

        user = EmpleadoAuthBackend().authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            user.backend = 'core.auth_backend.EmpleadoAuthBackend'

            empleado_autenticado = Empleado.objects.filter(
                pk=user.pk
            ).first()

            if (
                empleado_autenticado is None
                or not empleado_autenticado.activo
                or not getattr(user, 'is_active', True)
            ):
                messages.error(
                    request,
                    'Tu cuenta está desactivada. Por favor contactá al administrador.'
                )
                return render(request, 'panel/login.html')

            # Login exitoso: limpiar intentos fallidos
            limpiar_intentos_fallidos_login(username, ip_cliente)

            login(
                request,
                user,
                backend='core.auth_backend.EmpleadoAuthBackend'
            )

            # Configuración estricta de sesión de 12 horas (43.200 segundos)
            request.session['login_time'] = timezone.now().timestamp()
            request.session.set_expiry(43200)

            user.ultimo_login = timezone.now()
            user.save(update_fields=['last_login'])

            registrar_auditoria(
                request,
                'LOGIN',
                f'Inicio de sesión exitoso: {user.get_username()}'
            )

            if not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                next_url = reverse('panel_inicio')

            messages.success(
                request,
                f'¡Bienvenido/a, {user.nombre}!'
            )

            return redirect(next_url)

        intentos = registrar_intento_fallido_login(username, ip_cliente)
        registrar_auditoria(
            request,
            'LOGIN_FALLIDO',
            f'Intento fallido de login para: {username} desde IP: {ip_cliente} (intento #{intentos})'
        )

        if intentos >= 5:
            messages.error(
                request,
                'Has superado el límite de 5 intentos fallidos. Tu acceso ha sido bloqueado temporalmente por seguridad.'
            )
        else:
            intentos_restantes = 5 - intentos
            messages.error(
                request,
                f'Usuario/correo o contraseña incorrectos. Intentos restantes antes del bloqueo temporal: {intentos_restantes}.'
            )
        return render(request, 'panel/login.html')

    return render(request, 'panel/login.html')


def panel_logout(request):
    """
    Cierre de sesión seguro para usuarios del panel administrativo.
    """
    if getattr(request.user, 'is_authenticated', False):
        registrar_auditoria(request, 'LOGOUT', f'Cierre de sesión: {request.user.get_username()}')
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('panel_login')


def _enviar_correo_seguro(mensaje, correo):
    """Envía un correo capturando cualquier error (se usa en un hilo aparte)."""
    try:
        mensaje.send(fail_silently=False)
    except Exception as e:
        logger.exception("No se pudo enviar el correo a %s: %s", correo, e)


def panel_recuperar_contrasena(request):
    """
    Solicitud de restablecimiento de contraseña vía correo electrónico con token seguro,
    vencimiento temporal y uso único.
    Seguridad defensiva: no revela si un correo electrónico está o no registrado.
    """
    correo_enviado = False

    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip().lower()

        if correo:
            empleado = Empleado.objects.filter(correo__iexact=correo, activo=True).first()

            if empleado:
                token = secrets.token_urlsafe(32)
                expiracion = timezone.now() + timedelta(hours=2)

                empleado.token_recuperacion = token
                empleado.token_expiracion = expiracion
                empleado.save(update_fields=['token_recuperacion', 'token_expiracion'])

                enlace = request.build_absolute_uri(
                    reverse('panel_restablecer_contrasena', kwargs={'token': token})
                )

                contexto = {'nombre': empleado.nombre, 'enlace': enlace, 'horas': 2}

                registrar_auditoria(request, 'RECUPERACION_SOLICITADA', f'Solicitud de recuperación de contraseña para {correo}')

                try:
                    mensaje = EmailMultiAlternatives(
                        subject="Zona Burger - Recuperación de Contraseña",
                        body=render_to_string('emails/recuperar_contrasena.txt', contexto),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'Zona Burger <no-reply@zonaburger.com>'),
                        to=[empleado.correo],
                    )
                    mensaje.attach_alternative(
                        render_to_string('emails/recuperar_contrasena.html', contexto),
                        'text/html',
                    )
                    # El envío va en segundo plano: si el servidor de correo no responde
                    # (p. ej. SMTP bloqueado en el hosting) la petición no se cuelga ni da Error 500.
                    threading.Thread(
                        target=_enviar_correo_seguro, args=(mensaje, correo), daemon=True
                    ).start()
                except Exception as e:
                    logger.exception("Error al preparar correo de recuperación a %s: %s", correo, e)

            correo_enviado = True
            messages.success(
                request,
                'Si el correo electrónico ingresado corresponde a una cuenta activa registrada, '
                'recibirás un enlace con instrucciones para restablecer tu contraseña.'
            )

    return render(request, 'panel/recuperarContrasena.html', {'correo_enviado': correo_enviado})


_SECUENCIAS_DEBILES = ('0123456789', 'abcdefghijklmnopqrstuvwxyz', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm')


def _error_contrasena_nueva(contrasena, *datos_usuario):
    """Devuelve un mensaje de error si la contraseña no cumple las reglas (o None).

    datos_usuario (opcional): nombre, usuario o correo que la contraseña no debe contener.
    """
    if len(contrasena) < 8:
        return 'La nueva contraseña debe tener al menos 8 caracteres.'
    if len(contrasena) > 128:
        return 'La nueva contraseña no puede superar los 128 caracteres.'
    if any(c.isspace() for c in contrasena):
        return 'La contraseña no puede contener espacios.'
    if not any(c.isdigit() for c in contrasena):
        return 'La nueva contraseña debe incluir al menos un número.'
    if not any(c.islower() for c in contrasena):
        return 'La nueva contraseña debe incluir al menos una letra minúscula.'
    if not any(c.isupper() for c in contrasena):
        return 'La nueva contraseña debe incluir al menos una letra mayúscula.'
    if not any(not c.isalnum() for c in contrasena):
        return 'La nueva contraseña debe incluir al menos un símbolo (por ejemplo ! # $ % & *).'

    minus = contrasena.lower()
    if len(set(minus)) < 5:
        return 'La contraseña repite demasiado los mismos caracteres. Elegí una más variada.'
    for secuencia in _SECUENCIAS_DEBILES:
        for tramo in (secuencia, secuencia[::-1]):
            if any(tramo[i:i + 4] in minus for i in range(len(tramo) - 3)):
                return 'La contraseña contiene una secuencia fácil de adivinar (1234, abcd, qwer...).'
    for dato in datos_usuario:
        dato = (dato or '').strip().lower()
        if len(dato) >= 3 and dato in minus:
            return 'La contraseña no puede contener tu nombre, usuario o correo.'
    try:
        # Rechaza contraseñas débiles: demasiado comunes (password1, 12345678...) o solo números.
        CommonPasswordValidator().validate(contrasena)
        NumericPasswordValidator().validate(contrasena)
    except ValidationError:
        return 'La contraseña es demasiado débil o común. Elegí una más difícil de adivinar.'
    return None


def panel_restablecer_contrasena(request, token):
    """
    Permite establecer una nueva contraseña a partir de un token de recuperación válido y vigente.
    Invalida el token inmediatamente después del cambio para garantizar uso único.
    """
    empleado = Empleado.objects.filter(token_recuperacion=token).first()

    if not empleado or not empleado.token_expiracion or empleado.token_expiracion < timezone.now() or not empleado.activo:
        messages.error(
            request,
            'El enlace de recuperación es inválido o ha expirado. Por favor solicitá un nuevo enlace.'
        )
        return redirect('panel_recuperar_contrasena')

    if request.method == 'POST':
        nueva = request.POST.get('nueva_contrasena', '')
        confirmar = request.POST.get('confirmar_contrasena', '')

        if not nueva or not confirmar:
            messages.error(request, 'Por favor completá ambos campos.')
            return render(request, 'panel/restablecerContrasena.html', {'empleado': empleado, 'token': token})

        if nueva != confirmar:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'panel/restablecerContrasena.html', {'empleado': empleado, 'token': token})

        error_contrasena = _error_contrasena_nueva(nueva)
        if error_contrasena:
            messages.error(request, error_contrasena)
            return render(request, 'panel/restablecerContrasena.html', {'empleado': empleado, 'token': token})

        with transaction.atomic():
            empleado.contrasena = make_password(nueva)
            empleado.token_recuperacion = None
            empleado.token_expiracion = None
            empleado.save(update_fields=['contrasena', 'token_recuperacion', 'token_expiracion'])
            registrar_auditoria(request, 'RESTABLECER_CONTRASENA', f'Contraseña restablecida con token para {empleado.correo}')

        messages.success(request, 'Tu contraseña ha sido actualizada exitosamente. Ya podés iniciar sesión con tu nueva clave.')
        return redirect('panel_login')

    return render(request, 'panel/restablecerContrasena.html', {'empleado': empleado, 'token': token})


@panel_login_requerido
def panel_cambiar_contrasena(request):
    """
    Permite que cada usuario autenticado cambie su propia contraseña desde el panel,
    validando obligatoriamente su contraseña actual.
    """
    if request.method == 'POST':
        actual = request.POST.get('contrasena_actual', '')
        nueva = request.POST.get('nueva_contrasena', '')
        confirmar = request.POST.get('confirmar_contrasena', '')

        if not actual or not nueva or not confirmar:
            messages.error(request, 'Por favor completá todos los campos.')
            return render(request, 'panel/cambiarContrasena.html')

        if not check_password(actual, request.user.contrasena):
            messages.error(request, 'La contraseña actual ingresada es incorrecta.')
            return render(request, 'panel/cambiarContrasena.html')

        if nueva != confirmar:
            messages.error(request, 'La nueva contraseña y su confirmación no coinciden.')
            return render(request, 'panel/cambiarContrasena.html')

        error_contrasena = _error_contrasena_nueva(nueva)
        if error_contrasena:
            messages.error(request, error_contrasena)
            return render(request, 'panel/cambiarContrasena.html')

        if actual == nueva:
            messages.error(request, 'La nueva contraseña debe ser distinta a la contraseña actual.')
            return render(request, 'panel/cambiarContrasena.html')

        with transaction.atomic():
            request.user.contrasena = make_password(nueva)
            request.user.save(update_fields=['contrasena'])
            update_session_auth_hash(request, request.user)
            registrar_auditoria(request, 'CAMBIAR_CONTRASENA', f'Cambio de contraseña propio de {request.user.get_username()}')

        messages.success(request, 'Tu contraseña ha sido actualizada correctamente.')
        return redirect('panel_inicio')

    return render(request, 'panel/cambiarContrasena.html')


@panel_login_requerido
def panel_perfil(request):
    """Perfil del usuario: sus datos, su rol y los permisos que ese rol le da, agrupados por módulo."""
    permisos = Permiso.objects.filter(
        codigo__in=request.user.obtener_permisos()
    ).order_by('modulo', 'accion')

    por_modulo = {}
    for permiso in permisos:
        por_modulo.setdefault(permiso.modulo, []).append(permiso)

    return render(request, 'panel/perfil.html', {
        'usuario': request.user,
        'permisos_por_modulo': list(por_modulo.items()),
        'total_permisos': len(permisos),
    })


@requiere_permiso('usuarios.activar_desactivar')
@require_POST
def empleado_toggle_activo(request, idempleado):
    """
    Habilita o suspende una cuenta de usuario.
    Previene auto-desactivación para evitar bloqueos del sistema.
    """
    if getattr(request.user, 'pk', None) == idempleado:
        messages.error(request, 'Por motivos de seguridad no podés desactivar tu propia cuenta.')
        return redirect('empleado_lista')

    empleado = get_object_or_404(Empleado, pk=idempleado)
    nuevo_estado = not empleado.activo
    empleado.activo = nuevo_estado
    empleado.save(update_fields=['activo'])

    accion_texto = 'activada' if nuevo_estado else 'desactivada'
    registrar_auditoria(request, 'USUARIO_TOGGLE_ACTIVO', f'Cuenta de {empleado.correo} {accion_texto}')
    messages.success(request, f'La cuenta de {empleado.nombre} {empleado.apellido} fue {accion_texto} correctamente.')

    return redirect('empleado_lista')

def pagina_no_encontrada(request, exception=None):
    """Handler 404 global (aplica con DEBUG=False)."""
    return render(request, '404.html', status=404)


# 8b. PANEL - ELIMINAR INSUMO

def _motivos_bloqueo_insumo(insumo):
    """Lista de razones por las que un insumo no puede eliminarse (vacía si se puede)."""
    motivos = []
    if RecetaInsumo.objects.filter(idinsumo=insumo).exists():
        motivos.append('está siendo usado en una o más recetas')
    if DetalleCompra.objects.filter(idinsumo=insumo).exists():
        motivos.append('tiene compras registradas')
    if Opcion.objects.filter(idinsumo=insumo).exists():
        motivos.append('está vinculado a opciones de productos')
    if MovimientoStock.objects.filter(idinsumo=insumo, idpedido__isnull=False).exists():
        motivos.append('tiene movimientos de stock por pedidos')
    return motivos


@panel_login_requerido
@requiere_permiso('stock.eliminar', 'Eliminar insumos sin recetas ni compras asociadas')
def stock_eliminar(request, idinsumo):
    insumo = get_object_or_404(Insumo, pk=idinsumo)
    motivos = _motivos_bloqueo_insumo(insumo)

    if request.method == 'POST':
        if motivos:
            messages.error(
                request,
                f'No se puede eliminar "{insumo.nombreinsumo}" porque '
                + ' y '.join(motivos) + '.'
            )
            return redirect('stock_lista')

        nombre = insumo.nombreinsumo
        try:
            with transaction.atomic():
                MovimientoStock.objects.filter(idinsumo=insumo).delete()
                AjusteStock.objects.filter(idinsumo=insumo).delete()
                Lote.objects.filter(idinsumo=insumo).delete()
                insumo.delete()
                registrar_auditoria(request, 'INSUMO_ELIMINAR', f'Insumo "{nombre}" eliminado')
        except (IntegrityError, DatabaseError):
            logger.exception('No se pudo eliminar el insumo %s', idinsumo)
            messages.error(
                request,
                f'No se puede eliminar "{nombre}" porque tiene registros relacionados.'
            )
            return redirect('stock_lista')

        messages.success(request, f'El insumo "{nombre}" fue eliminado correctamente.')
        return redirect('stock_lista')

    return render(
        request,
        'panel/stock/stockEliminar.html',
        {'insumo': insumo, 'motivos': motivos},
    )


# 11. PANEL - REGISTRO DE AUDITORÍA

ETIQUETAS_AUDITORIA = {
    'LOGIN': 'Inicio de sesión',
    'LOGIN_FALLIDO': 'Intento de inicio de sesión fallido',
    'LOGOUT': 'Cierre de sesión',
    'CAMBIAR_CONTRASENA': 'Cambio de contraseña propio',
    'RECUPERACION_SOLICITADA': 'Recuperación de contraseña solicitada',
    'RESTABLECER_CONTRASENA': 'Contraseña restablecida',
    'USUARIO_EDITAR': 'Usuario modificado',
    'USUARIO_TOGGLE_ACTIVO': 'Usuario activado / desactivado',
    'INSUMO_ELIMINAR': 'Insumo eliminado',
    'LOTE_BAJA': 'Lote dado de baja',
    'PRODUCTO_ELIMINAR': 'Producto eliminado',
    'NEGOCIO_ABRIR': 'Negocio abierto',
    'NEGOCIO_CERRAR': 'Negocio cerrado',
}


def _acciones_auditoria():
    """Acciones para el desplegable: las conocidas más las que ya hay registradas."""
    codigos = set(ETIQUETAS_AUDITORIA) | set(
        RegistroAuditoria.objects.values_list('accion', flat=True).distinct()
    )
    return sorted(
        ((c, ETIQUETAS_AUDITORIA.get(c, c.replace('_', ' ').capitalize())) for c in codigos),
        key=lambda par: par[1].lower(),
    )


@panel_login_requerido
@requiere_permiso('auditoria.ver', 'Consultar el registro de auditoría de acciones críticas')
def auditoria_lista(request):
    registros = RegistroAuditoria.objects.select_related('idempleado').order_by('-fecha', '-idauditoria')

    accion = request.GET.get('accion', '').strip()
    usuario = request.GET.get('usuario', '').strip()
    desde = parse_date(request.GET.get('desde', '').strip() or '')
    hasta = parse_date(request.GET.get('hasta', '').strip() or '')

    if accion:
        registros = registros.filter(accion__iexact=accion)
    if usuario:
        registros = registros.filter(
            Q(idempleado__correo__icontains=usuario)
            | Q(idempleado__nombre__icontains=usuario)
            | Q(idempleado__apellido__icontains=usuario)
        )
    if desde:
        registros = registros.filter(fecha__date__gte=desde)
    if hasta:
        registros = registros.filter(fecha__date__lte=hasta)

    pagina = Paginator(registros, 50).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'panel/administracion/auditoria/auditoriaLista.html', {
        'pagina': pagina,
        'filtros': {'accion': accion, 'usuario': usuario,
                    'desde': request.GET.get('desde', ''), 'hasta': request.GET.get('hasta', '')},
        'querystring': params.urlencode(),
        'acciones': _acciones_auditoria(),
    })