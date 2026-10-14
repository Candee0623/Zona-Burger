import logging
from decimal import Decimal
from django.db import transaction
from .models import (
    Insumo, Opcion, RecetaInsumo, Pedido, DetallePedido, MovimientoStock
)

logger = logging.getLogger(__name__)


class StockInsuficienteError(Exception):
    """Excepción lanzada cuando uno o más insumos no tienen stock suficiente."""
    def __init__(self, insumo, disponible, necesario):
        self.insumo = insumo
        self.disponible = disponible
        self.necesario = necesario
        super().__init__(
            f"Stock insuficiente de {insumo.nombreinsumo}. "
            f"Disponible: {disponible}. Necesario: {necesario}."
        )


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

            consumo[insumo.pk]['cantidad'] += cantidad_receta * Decimal(str(cantidad_producto))

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
            cantidad_total_opcion = cant_por_opcion * Decimal(str(cantidad_producto))

            if insumo_opcion.pk not in consumo:
                consumo[insumo_opcion.pk] = {
                    'insumo': insumo_opcion,
                    'cantidad': Decimal('0.00'),
                    'detalle': f"Opción '{opcion.nombre}' (x{cant_por_opcion})",
                }

            consumo[insumo_opcion.pk]['cantidad'] += cantidad_total_opcion

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
                f"Disponible: {insumo.stockactual}. Necesario: {cantidad_necesaria}."
            )
    return len(errores) == 0, errores


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

        # Descontar stock y registrar movimientos
        for insumo_id, dato in consumo_insumos.items():
            insumo = insumos_bloqueados[insumo_id]
            cantidad = dato['cantidad']
            insumo.stockactual -= cantidad
            insumo.save(update_fields=['stockactual'])

            MovimientoStock.objects.create(
                idinsumo=insumo,
                cantidad=cantidad,
                idpedido=pedido,
                tipomovimiento=MovimientoStock.TIPO_DESCUENTO,
                descripcion=f"Descuento automático por Pedido #{pedido.idpedido}. {dato.get('detalle', '')}".strip(),
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

            MovimientoStock.objects.create(
                idinsumo=insumo,
                cantidad=mov.cantidad,
                idpedido=pedido,
                tipomovimiento=MovimientoStock.TIPO_REINTEGRO,
                descripcion=f"Reintegro por cancelación de Pedido #{pedido.idpedido}. Motivo: {motivo}".strip(),
            )

        pedido.stock_descontado = False
        pedido.save(update_fields=['stock_descontado'])

    logger.info("Stock reintegrado exitosamente para el pedido #%s.", pedido.idpedido)
    return True, "Stock reintegrado exitosamente."
