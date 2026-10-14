# Generated manually to reconcile Insumo.DescontarStockAutomaticamente between database and state.

from django.db import migrations

SQL_FORWARD = """
IF NOT EXISTS (
    SELECT 1 
    FROM sys.columns 
    WHERE object_id = OBJECT_ID(N'[dbo].[Insumo]') 
      AND name = 'DescontarStockAutomaticamente'
)
BEGIN
    ALTER TABLE [dbo].[Insumo] 
    ADD [DescontarStockAutomaticamente] BIT NOT NULL 
    CONSTRAINT [DF_Insumo_DescontarStockAutomaticamente] DEFAULT (0);

    EXEC sys.sp_addextendedproperty 
        @name = N'CreatedByMigration0018', 
        @value = N'1', 
        @level0type = N'SCHEMA', @level0name = N'dbo', 
        @level1type = N'TABLE',  @level1name = N'Insumo', 
        @level2type = N'COLUMN', @level2name = N'DescontarStockAutomaticamente';
END
"""

SQL_REVERSE = """
-- Solo se elimina la columna si fue creada específicamente por esta migración (marcada con la propiedad extendida).
-- Si la columna ya existía antes de aplicar esta migración, la reversión NO la elimina para proteger datos preexistentes.
IF EXISTS (
    SELECT 1 
    FROM sys.extended_properties ep
    INNER JOIN sys.columns c ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
    WHERE ep.major_id = OBJECT_ID(N'[dbo].[Insumo]')
      AND c.name = 'DescontarStockAutomaticamente'
      AND ep.name = N'CreatedByMigration0018'
)
BEGIN
    DECLARE @ConstraintName NVARCHAR(200);
    SELECT @ConstraintName = dc.name 
    FROM sys.default_constraints dc
    INNER JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    WHERE dc.parent_object_id = OBJECT_ID(N'[dbo].[Insumo]')
      AND c.name = 'DescontarStockAutomaticamente';

    IF @ConstraintName IS NOT NULL
    BEGIN
        EXEC('ALTER TABLE [dbo].[Insumo] DROP CONSTRAINT [' + @ConstraintName + ']');
    END

    EXEC sys.sp_dropextendedproperty 
        @name = N'CreatedByMigration0018', 
        @level0type = N'SCHEMA', @level0name = N'dbo', 
        @level1type = N'TABLE',  @level1name = N'Insumo', 
        @level2type = N'COLUMN', @level2name = N'DescontarStockAutomaticamente';

    ALTER TABLE [dbo].[Insumo] DROP COLUMN [DescontarStockAutomaticamente];
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_opcion_insumo_movimientostock'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=SQL_FORWARD,
                    reverse_sql=SQL_REVERSE,
                ),
            ],
            state_operations=[],
        ),
    ]
