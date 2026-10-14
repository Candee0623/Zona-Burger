# Zona Burger

Aplicación web desarrollada con **Django y SQL Server** para gestionar productos, stock, clientes, pedidos y promociones.

## Requisitos

- Windows y Python 3.13 de 64 bits.
- Git y VS Code.
- SQL Server 2022 Express y SSMS.
- ODBC Driver 17 for SQL Server de 64 bits.
- Archivo `ZonaBurger.sql` compatible con la versión del proyecto.

## 1. Descargar el proyecto

-powershell
git clone https://github.com/Candee0623/Zona-Burger.git


-powershell
cd Zona-Burger


Abrir esa carpeta en VS Code. Ejecutar los siguientes comandos desde la carpeta donde está `manage.py`, uno por uno.

## 2. Instalar las dependencias

-powershell
py -3.13 -m venv .venv


-powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt


Estos comandos usan directamente el entorno virtual; no es necesario activarlo.

## 3. Importar la base de datos

Conectarse a SQL Server desde SSMS con **Autenticación de Windows**.

Comprobar si la base ya existe:

-sql
SELECT name FROM sys.databases WHERE name = N'ZonaBurger';


**Si existe, no importar nuevamente el archivo completo.** Revisar la instalación anterior.

Para una base nueva, abrir `ZonaBurger.sql`. Reemplazar el bloque inicial completo, desde `USE [master]` hasta el `GO` posterior a `SET COMPATIBILITY_LEVEL = 160`, por:

-sql

USE [master]
GO
CREATE DATABASE [ZonaBurger]
GO
ALTER DATABASE [ZonaBurger] SET COMPATIBILITY_LEVEL = 160
GO


Conservar el resto del archivo y ejecutarlo completo con **F5**. El bloque reemplazado no debe conservar las rutas `.mdf` y `.ldf` ni `LOG ON`.

**Si aparece un error, detenerse y no repetir la importación completa.** El SQL debe corresponder a la versión del código; las migraciones actuales no garantizan toda la estructura desde cero.

## 4. Crear el archivo .env

Crear `.env` junto a `manage.py` con este contenido:

-dotenv

SECRET_KEY=zona-burger-clave-solo-para-pruebas-locales
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=ZonaBurger
DB_HOST=NOMBRE-DE-TU-PC\SQLEXPRESS
DB_PORT=
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_TRUSTED_CONNECTION=yes

Reemplazar `DB_HOST` por el servidor utilizado en SSMS. Esta clave es solo para pruebas locales. No subir `.env` a GitHub.

## 5. Verificar y sincronizar migraciones

-powershell
.\.venv\Scripts\python.exe manage.py check

-powershell
.\.venv\Scripts\python.exe manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('Conexión correcta')"

-powershell
.\.venv\Scripts\python.exe manage.py showmigrations


**Solo para una instalación nueva con el SQL compatible importado sin errores y el historial vacío (`[ ]`):**

-powershell
.\.venv\Scripts\python.exe manage.py migrate --fake


-powershell
.\.venv\Scripts\python.exe manage.py migrate


`--fake` registra las migraciones sin crear tablas. No usarlo sobre una base vacía, una importación parcial o un esquema de otra versión.

## 6. Cargar datos iniciales

Ejecutar:

-powershell
.\.venv\Scripts\python.exe manage.py cargar_datos_iniciales


La carga inicial agrega:

- Estados de productos y pedidos.
- Medios de pago.
- Datos del negocio.
- Zonas de entrega.

**No agrega productos ni categorías:** se cargan después desde el panel. Puede actualizar algunos datos existentes del negocio y las zonas.

## 7. Crear un administrador

-powershell
.\.venv\Scripts\python.exe manage.py createsuperuser


Seguir las instrucciones de usuario, correo y contraseña. Al escribir la contraseña no se muestran caracteres; es normal.

## 8. Ejecutar la aplicación

-powershell
.\.venv\Scripts\python.exe manage.py runserver 8002


| Acceso | Dirección |
| Aplicación | [Página principal](http://127.0.0.1:8002/) |
| Panel de Zona Burger | [Panel](http://127.0.0.1:8002/panel/) |
| Administración de Django | [Administrador](http://127.0.0.1:8002/admin/) |

Dejar la terminal abierta. Para detener el servidor, presionar **Ctrl + C**. En las próximas sesiones solo hace falta iniciar el servidor.

## Actualizar el proyecto con Git

Detener el servidor. Si `git status --short` no muestra cambios propios, ejecutar:

-powershell
git pull --ff-only


-powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt


-powershell
.\.venv\Scripts\python.exe manage.py check


-powershell
.\.venv\Scripts\python.exe manage.py migrate --plan


Si hay cambios pendientes en la base, seguir las instrucciones de actualización del proyecto. No repetir `--fake` ni importar nuevamente todo el SQL automáticamente.
