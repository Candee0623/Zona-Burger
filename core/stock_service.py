import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import (
    AjusteStock, Insumo, Lote, Opcion, RecetaInsumo, Pedido, DetallePedido,
    MovimientoStock,
)

logger = logging.getLogger(__name__)


CUATRO_DECIMALES = Decimal('0.0001')

TIPO_CARGA_INICIAL = 'CARGA_INICIAL'
TIPO_BAJA_LOTE = 'BAJA_LOTE'


def _a_decimales_stock(cantidad):
    """Redondea a los 4 decimales que guarda la base para el stock."""
    return Decimal(cantidad).quantize(CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


def _unidad_stock(insumo):
    return insumo.unidadmedidaingreso or ''


def cantidad_a_unidad_stock(insumo, cantidad, unidad_origen=None):
    """
    Convierte `cantidad` (expresada en `unidad_origen`, por defecto la unidad de egreso
    del insumo) a la unidad en la que se guarda el stock (unidad de ingreso).
    Ej.: 150 g de un insumo que se compra en kg -> 0,15 kg.
    Si las unidades no son convertibles y no hay equivalencia cargada se deja la
    cantidad tal cual y se avisa en el log (comportamiento anterior).
    """
    factor = insumo.factor_a_stock(unidad_origen)

    if factor is None and unidad_origen:
        # La unidad guardada en la receta no se reconoce (por ejemplo el valor
        # por defecto 'unidad' en recetas viejas): la cantidad se interpreta en
        # la unidad de egreso del insumo, que es la que se carga en el panel.
        factor = insumo.factor_a_stock(None)

    if factor is None:
        logger.warning(
            "No se pueden convertir '%s' a '%s' para el insumo '%s' (ID %s). "
            "Cargá la equivalencia en el insumo.",
            unidad_origen or insumo.unidadmedidaegreso,
            insumo.unidadmedidaingreso,
            insumo.nombreinsumo,
            insumo.pk,
        )
        factor = Decimal('1')

    return Decimal(cantidad) * factor


class StockCambiadoError(Exception):
    """El stock del insumo cambió entre que se abrió el ajuste y se guardó."""
    def __init__(self, insumo, actual):
        self.insumo = insumo
        self.actual = actual
        super().__init__(
            f"El stock de {insumo.nombreinsumo} cambió mientras hacías el ajuste "
            f"(ahora es {_fmt(actual)} {_unidad_stock(insumo)}). "
            "Revisá la cantidad y volvé a intentar."
        )


class StockInsuficienteError(Exception):
    """Excepción lanzada cuando uno o más insumos no tienen stock suficiente."""
    def __init__(self, insumo, disponible, necesario):
        self.insumo = insumo
        self.disponible = disponible
        self.necesario = necesario
        super().__init__(
            f"Stock insuficiente de {insumo.nombreinsumo}. "
            f"Disponible: {_fmt(disponible)} {_unidad_stock(insumo)}. "
            f"Necesario: {_fmt(necesario)} {_unidad_stock(insumo)}."
        )


def _fmt(cantidad):
    """4 decimales máximo, sin ceros de más (0.1500 -> 0.15)."""
    texto = f"{Decimal(cantidad):.4f}".rstrip('0').rstrip('.')
    return texto or '0'


def calcular_consumo_carrito(carrito):
    """
    Calcula el consumo total de insumos del carrito de compras:
    1. Insumos base definidos en la receta del producto (descontando ingredientes quitados por el cliente).
    2. Insumos vinculados a las opciones seleccionadas (ej: Bebida Sprite -> Insumo Sprite),
       multiplicados por la cantidad del producto y la cantidad configurada para la opción.

    Solo se consideran los insumos que tengan 'descontar_stock_automaticamente=True'.
    Las opciones sin insumo vinculado se omiten de forma segura informando en log.
    """
    consumo = {}

    for item in carrito.values():
        producto_id = item.get('producto_id')
        try:
            cantidad_producto = int(item.get('cantidad', 1) or 1)
        except (ValueError, TypeError):
            cantidad_producto = 1

        if not producto_id or cantidad_producto <= 0:
            continue

        # 1. Insumos quitados por personalización ('Sin cebolla', etc.)
        insumos_quitados = {
            str(insumo_id)
            for insumo_id in item.get('insumos_quitados_ids', [])
        }

        # Insumos de la receta base del producto
        recetas = (
            RecetaInsumo.objects
            .filter(
                idreceta__idproducto_id=producto_id,
                idinsumo__isnull=False,
                idreceta__isnull=False,
                idinsumo__descontar_stock_automaticamente=True,
            )
            .select_related('idinsumo')
        )

        for detalle_receta in recetas:
            insumo = detalle_receta.idinsumo
            if str(insumo.pk) in insumos_quitados:
                continue

            cantidad_receta = detalle_receta.cantidadinsumo or Decimal('0.00')
            if cantidad_receta <= 0:
                continue

            if insumo.pk not in consumo:
                consumo[insumo.pk] = {
                    'insumo': insumo,
                    'cantidad': Decimal('0.00'),
                    'detalle': f"Receta base de producto #{producto_id}",
                }

            # La receta está en su propia unidad (ej. g); el stock en la de ingreso (ej. kg).
            cantidad_receta_stock = cantidad_a_unidad_stock(
                insumo, cantidad_receta, detalle_receta.unidadmedida
            )
            consumo[insumo.pk]['cantidad'] += (
                cantidad_receta_stock * Decimal(str(cantidad_producto))
            )

        # 2. Insumos de opciones seleccionadas (ej: Sprite, Coca-Cola, etc.)
        opciones_ids = item.get('opciones_ids', [])
        for opc_id in opciones_ids:
            try:
                opcion = (
                    Opcion.objects
                    .filter(pk=opc_id)
                    .select_related('idinsumo')
                    .first()
                )
            except Exception:
                opcion = None

            if not opcion:
                continue

            if not opcion.idinsumo:
                logger.info(
                    "La opción '%s' (ID %s) no tiene un insumo de stock vinculado. No se descuenta inventario.",
                    opcion.nombre,
                    opcion.idopcion,
                )
                continue

            insumo_opcion = opcion.idinsumo
            if not insumo_opcion.descontar_stock_automaticamente:
                logger.info(
                    "El insumo '%s' vinculado a la opción '%s' tiene desactivado el descuento automático.",
                    insumo_opcion.nombreinsumo,
                    opcion.nombre,
                )
                continue

            cant_por_opcion = opcion.cantidad_insumo if opcion.cantidad_insumo and opcion.cantidad_insumo > 0 else Decimal('1.00')
            # La cantidad de la opción se expresa en la unidad de egreso del insumo.
            cant_por_opcion_stock = cantidad_a_unidad_stock(insumo_opcion, cant_por_opcion)
            cantidad_total_opcion = cant_por_opcion_stock * Decimal(str(cantidad_producto))

            if insumo_opcion.pk not in consumo:
                consumo[insumo_opcion.pk] = {
                    'insumo': insumo_opcion,
                    'cantidad': Decimal('0.00'),
                    'detalle': f"Opción '{opcion.nombre}' (x{cant_por_opcion})",
                }

            consumo[insumo_opcion.pk]['cantidad'] += cantidad_total_opcion

    for dato in consumo.values():
        dato['cantidad'] = _a_decimales_stock(dato['cantidad'])

    return consumo


def verificar_stock_disponible(consumo):
    """
    Verifica que todos los insumos requeridos tengan stock disponible suficiente.
    Devuelve (True, []) si hay stock suficiente, o (False, [mensajes_error]) si falta stock.
    """
    errores = []
    for insumo_id, dato in consumo.items():
        insumo = dato['insumo']
        cantidad_necesaria = dato['cantidad']
        if insumo.stockactual < cantidad_necesaria:
            errores.append(
                f"Stock insuficiente de {insumo.nombreinsumo}. "
                f"Disponible: {_fmt(insumo.stockactual)} {_unidad_stock(insumo)}. "
                f"Necesario: {_fmt(cantidad_necesaria)} {_unidad_stock(insumo)}."
            )
    return len(errores) == 0, errores


def _orden_fefo(lote, hoy):
    """
    Primero vence, primero sale (FEFO): los lotes vigentes con fecha de vencimiento más
    próxima van primero, después los que no tienen fecha y por último los ya vencidos.
    """
    vencido = bool(lote.fechavencimiento and lote.fechavencimiento < hoy)
    return (
        vencido,
        lote.fechavencimiento is None,
        lote.fechavencimiento or date.max,
        lote.fechaingreso,
        lote.pk,
    )


def consumir_lotes(insumo, cantidad):
    """
    Resta `cantidad` (en unidad de stock) de los lotes del insumo siguiendo FEFO.
    Debe llamarse dentro de una transacción. Devuelve [(lote, cantidad_tomada), ...].
    Si los lotes no alcanzan (datos viejos que no cuadran) el resto se devuelve con
    lote None para que igual quede registrado el movimiento.
    """
    restante = Decimal(cantidad)
    if restante <= 0:
        return []

    hoy = timezone.localdate()
    lotes = sorted(
        Lote.objects.select_for_update().filter(idinsumo=insumo, cantidadactual__gt=0),
        key=lambda l: _orden_fefo(l, hoy),
    )

    tomados = []
    for lote in lotes:
        if restante <= 0:
            break
        tomar = min(lote.cantidadactual, restante)
        lote.cantidadactual -= tomar
        lote.save(update_fields=['cantidadactual'])
        restante -= tomar
        tomados.append((lote, tomar))

    if restante > 0:
        tomados.append((None, restante))

    return tomados


def registrar_ingreso_lote(insumo, cantidad, fecha_vencimiento=None,
                           tipo_movimiento=MovimientoStock.TIPO_COMPRA, descripcion=''):
    """
    Da entrada a stock creando un lote (con su fecha de vencimiento) y sumando al insumo.
    `insumo` debe estar bloqueado (select_for_update) dentro de una transacción.
    """
    cantidad = _a_decimales_stock(cantidad)
    ahora = timezone.now()

    lote = Lote.objects.create(
        idinsumo=insumo,
        fechaingreso=ahora,
        fechavencimiento=fecha_vencimiento,
        cantidadinicial=cantidad,
        cantidadactual=cantidad,
    )

    insumo.stockactual = (insumo.stockactual or Decimal('0')) + cantidad
    insumo.save(update_fields=['stockactual'])

    MovimientoStock.objects.create(
        idinsumo=insumo,
        idlote=lote,
        cantidad=cantidad,
        idpedido=None,
        tipomovimiento=tipo_movimiento,
        descripcion=(descripcion or f"Ingreso de {insumo.nombreinsumo}")[:250],
    )
    return lote


@transaction.atomic
def ajustar_stock_insumo(insumo_id, cantidad_nueva, motivo, fecha_vencimiento=None,
                         empleado=None, stock_esperado=None):
    """
    Ajuste manual de inventario manteniendo lotes y stock sincronizados:
    - si sobra stock físico de más, se crea un lote nuevo por la diferencia;
    - si falta, se descuenta de los lotes por orden de vencimiento.
    Guarda quién hizo el ajuste y el lote afectado.
    Si se indica `stock_esperado` (el stock que veía la persona al abrir el ajuste)
    y el stock cambió mientras tanto, no se pisa el cambio: se lanza StockCambiadoError.
    """
    insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
    anterior = insumo.stockactual or Decimal('0')

    if stock_esperado is not None and _a_decimales_stock(stock_esperado) != _a_decimales_stock(anterior):
        raise StockCambiadoError(insumo, anterior)

    nueva = _a_decimales_stock(cantidad_nueva)
    diferencia = nueva - anterior

    ajuste = AjusteStock.objects.create(
        idinsumo=insumo,
        cantidadanterior=anterior,
        cantidadnueva=nueva,
        motivo=motivo,
        idempleado=empleado,
    )
    lote_ajuste = None

    if diferencia > 0:
        lote_ajuste = registrar_ingreso_lote(
            insumo, diferencia, fecha_vencimiento,
            tipo_movimiento=MovimientoStock.TIPO_AJUSTE,
            descripcion=f"Ajuste de inventario (+). Motivo: {motivo}"[:250],
        )
    elif diferencia < 0:
        for lote, cantidad_lote in consumir_lotes(insumo, -diferencia):
            if lote_ajuste is None and lote is not None:
                lote_ajuste = lote
            MovimientoStock.objects.create(
                idinsumo=insumo,
                idlote=lote,
                cantidad=cantidad_lote,
                idpedido=None,
                tipomovimiento=MovimientoStock.TIPO_AJUSTE,
                descripcion=f"Ajuste de inventario (-). Motivo: {motivo}"[:250],
            )
        insumo.stockactual = nueva
        insumo.save(update_fields=['stockactual'])

    if lote_ajuste is not None:
        ajuste.idlote = lote_ajuste
        ajuste.save(update_fields=['idlote'])

    return insumo, diferencia


@transaction.atomic
def dar_baja_lote(lote_id, motivo='Lote vencido'):
    """Descarta lo que queda de un lote (por vencimiento o merma) y lo resta del stock."""
    lote = Lote.objects.select_for_update().get(pk=lote_id)
    insumo = Insumo.objects.select_for_update().get(pk=lote.idinsumo_id)
    cantidad = lote.cantidadactual or Decimal('0')

    if cantidad <= 0:
        return lote, Decimal('0')

    lote.cantidadactual = Decimal('0')
    lote.save(update_fields=['cantidadactual'])

    insumo.stockactual = max((insumo.stockactual or Decimal('0')) - cantidad, Decimal('0'))
    insumo.save(update_fields=['stockactual'])

    MovimientoStock.objects.create(
        idinsumo=insumo,
        idlote=lote,
        cantidad=cantidad,
        idpedido=None,
        tipomovimiento=TIPO_BAJA_LOTE,
        descripcion=f"Baja del lote {lote.codigo}. Motivo: {motivo}"[:250],
    )
    return lote, cantidad


def descontar_stock_pedido(pedido, consumo_insumos=None):
    """
    Descuenta automáticamente el stock correspondiente a un pedido.
    Aplica controles de idempotencia para garantizar que NO se descuente dos veces:
    - Si pedido.stock_descontado ya es True, no realiza ninguna acción.
    - Bloquea los insumos en una transacción atómica (select_for_update).
    - Valida disponibilidad antes de descontar.
    - Registra cada movimiento en la tabla MovimientoStock con tipo 'DESCUENTO'.
    - Marca pedido.stock_descontado = True.
    """
    if pedido.stock_descontado:
        logger.warning(
            "Intento de descuento duplicado para el pedido #%s. Operación ignorada.",
            pedido.idpedido,
        )
        return False, "El stock de este pedido ya fue descontado."

    if consumo_insumos is None:
        logger.warning("No se proporcionó consumo_insumos para el pedido #%s.", pedido.idpedido)
        return False, "No hay insumos para descontar."

    if not consumo_insumos:
        # No hay insumos automáticos para este pedido (ej: productos sin receta ni opciones con stock)
        pedido.stock_descontado = True
        pedido.save(update_fields=['stock_descontado'])
        return True, "No había insumos automáticos para descontar."

    with transaction.atomic():
        insumos_bloqueados = {}
        for insumo_id in sorted(consumo_insumos.keys()):
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
            cantidad_necesaria = consumo_insumos[insumo_id]['cantidad']

            if insumo.stockactual < cantidad_necesaria:
                raise StockInsuficienteError(
                    insumo=insumo,
                    disponible=insumo.stockactual,
                    necesario=cantidad_necesaria,
                )
            insumos_bloqueados[insumo_id] = insumo

        # Descontar stock (y lotes por orden de vencimiento) y registrar movimientos
        for insumo_id, dato in consumo_insumos.items():
            insumo = insumos_bloqueados[insumo_id]
            cantidad = dato['cantidad']
            insumo.stockactual -= cantidad
            insumo.save(update_fields=['stockactual'])

            detalle = f"Descuento automático por Pedido #{pedido.idpedido}. {dato.get('detalle', '')}".strip()
            for lote, cantidad_lote in consumir_lotes(insumo, cantidad):
                MovimientoStock.objects.create(
                    idinsumo=insumo,
                    idlote=lote,
                    cantidad=cantidad_lote,
                    idpedido=pedido,
                    tipomovimiento=MovimientoStock.TIPO_DESCUENTO,
                    descripcion=(
                        f"{detalle} Lote {lote.codigo}." if lote else detalle
                    )[:250],
                )

        pedido.stock_descontado = True
        pedido.save(update_fields=['stock_descontado'])

    logger.info("Stock descontado exitosamente para el pedido #%s.", pedido.idpedido)
    return True, "Stock descontado exitosamente."


def reintegrar_stock_pedido(pedido, motivo="Cancelación de pedido"):
    """
    Reintegra automáticamente el stock previamente descontado de un pedido cancelado.
    Controles para evitar reintegros duplicados o incorrectos:
    - Si pedido.stock_descontado es False, no realiza nada.
    - Consulta los movimientos de tipo 'DESCUENTO' registrados para este pedido.
    - Reintegra cada insumo en una transacción atómica.
    - Registra el movimiento inverso con tipo 'REINTEGRO'.
    - Marca pedido.stock_descontado = False.
    """
    if not pedido.stock_descontado:
        logger.info(
            "El pedido #%s no tiene stock descontado; no se requiere reintegro.",
            pedido.idpedido,
        )
        return False, "El pedido no tenía stock descontado."

    movimientos_descuento = MovimientoStock.objects.filter(
        idpedido=pedido,
        tipomovimiento=MovimientoStock.TIPO_DESCUENTO,
    )

    if not movimientos_descuento.exists():
        # No se registraron movimientos específicos, marcar como no descontado
        pedido.stock_descontado = False
        pedido.save(update_fields=['stock_descontado'])
        return True, "No se encontraron movimientos de descuento registrados para este pedido."

    with transaction.atomic():
        for mov in movimientos_descuento:
            insumo = Insumo.objects.select_for_update().get(pk=mov.idinsumo_id)
            insumo.stockactual += mov.cantidad
            insumo.save(update_fields=['stockactual'])

            lote = None
            if mov.idlote_id:
                lote = Lote.objects.select_for_update().filter(pk=mov.idlote_id).first()
                if lote:
                    lote.cantidadactual += mov.cantidad
                    lote.save(update_fields=['cantidadactual'])

            MovimientoStock.objects.create(
                idinsumo=insumo,
                idlote=lote,
                cantidad=mov.cantidad,
                idpedido=pedido,
                tipomovimiento=MovimientoStock.TIPO_REINTEGRO,
                descripcion=f"Reintegro por cancelación de Pedido #{pedido.idpedido}. Motivo: {motivo}".strip()[:250],
            )

        pedido.stock_descontado = False
        pedido.save(update_fields=['stock_descontado'])

    logger.info("Stock reintegrado exitosamente para el pedido #%s.", pedido.idpedido)
    return True, "Stock reintegrado exitosamente."