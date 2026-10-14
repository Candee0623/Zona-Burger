-- ============================================================================
-- SCRIPT DE MIGRACIÓN SQL SERVER - ZONA BURGER
-- Módulo de Stock: Integración de Opciones de Productos y Movimientos de Stock
-- ============================================================================

USE [ZonaBurger];
GO

-- 1. Agregar columna IdInsumo a la tabla Opcion (si no existe)
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('Opcion') AND name = 'IdInsumo'
)
BEGIN
    ALTER TABLE [dbo].[Opcion]
    ADD [IdInsumo] INT NULL;

    ALTER TABLE [dbo].[Opcion]
    ADD CONSTRAINT [FK_Opcion_Insumo]
    FOREIGN KEY ([IdInsumo]) REFERENCES [dbo].[Insumo]([IdInsumo]);

    PRINT 'Columna IdInsumo agregada a la tabla Opcion con su clave foránea.';
END
ELSE
BEGIN
    PRINT 'La columna IdInsumo ya existe en la tabla Opcion.';
END
GO

-- 2. Agregar columna CantidadInsumo a la tabla Opcion (si no existe)
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('Opcion') AND name = 'CantidadInsumo'
)
BEGIN
    ALTER TABLE [dbo].[Opcion]
    ADD [CantidadInsumo] DECIMAL(10, 2) NOT NULL CONSTRAINT [DF_Opcion_CantidadInsumo] DEFAULT (1.00);

    PRINT 'Columna CantidadInsumo agregada a la tabla Opcion con valor por defecto 1.00.';
END
ELSE
BEGIN
    PRINT 'La columna CantidadInsumo ya existe en la tabla Opcion.';
END
GO

-- 3. Agregar columna StockDescontado a la tabla Pedido (si no existe)
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('Pedido') AND name = 'StockDescontado'
)
BEGIN
    ALTER TABLE [dbo].[Pedido]
    ADD [StockDescontado] BIT NOT NULL CONSTRAINT [DF_Pedido_StockDescontado] DEFAULT (0);

    PRINT 'Columna StockDescontado agregada a la tabla Pedido con valor por defecto 0.';
END
ELSE
BEGIN
    PRINT 'La columna StockDescontado ya existe en la tabla Pedido.';
END
GO

-- 4. Crear tabla MovimientoStock (si no existe)
IF NOT EXISTS (
    SELECT 1 FROM sys.tables 
    WHERE name = 'MovimientoStock'
)
BEGIN
    CREATE TABLE [dbo].[MovimientoStock] (
        [IdMovimiento] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [IdInsumo] INT NOT NULL,
        [Cantidad] DECIMAL(10, 2) NOT NULL,
        [IdPedido] INT NULL,
        [Fecha] DATETIME NOT NULL CONSTRAINT [DF_MovimientoStock_Fecha] DEFAULT (GETDATE()),
        [TipoMovimiento] VARCHAR(50) NOT NULL, -- 'DESCUENTO', 'REINTEGRO', 'AJUSTE', 'COMPRA'
        [Descripcion] VARCHAR(250) NULL,
        CONSTRAINT [FK_MovimientoStock_Insumo] FOREIGN KEY ([IdInsumo]) REFERENCES [dbo].[Insumo]([IdInsumo]),
        CONSTRAINT [FK_MovimientoStock_Pedido] FOREIGN KEY ([IdPedido]) REFERENCES [dbo].[Pedido]([IdPedido])
    );

    PRINT 'Tabla MovimientoStock creada exitosamente.';
END
ELSE
BEGIN
    PRINT 'La tabla MovimientoStock ya existe.';
END
GO

PRINT 'Actualización de base de datos finalizada correctamente.';
GO
