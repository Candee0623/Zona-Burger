# Zona-Burger

Aplicación web para la gestión de un negocio gastronómico, desarrollada con **Django** y **SQL Server**.

El sistema permite gestionar productos, categorías, extras, opciones, stock, compras, recetas, clientes, pedidos, medios de pago, promociones y demás información relacionada con el funcionamiento de Zona-Burger.

## Tecnologías utilizadas

* Python
* Django 6.1
* Microsoft SQL Server
* mssql-django
* pyodbc
* Pillow
* django-ckeditor-5
* django-jazzmin
* python-dotenv

## Estructura del proyecto

El proyecto está organizado de la siguiente manera:

* `manage.py` — archivo principal para ejecutar comandos de Django.
* `ZonaBurger/` — configuración principal del proyecto.
* `core/` — aplicación principal que contiene modelos, vistas, formularios, URLs, templates y comandos personalizados.
* `core/migrations/` — migraciones de la base de datos.
* `core/management/commands/cargar_datos_iniciales.py` — comando para cargar automáticamente los datos básicos necesarios para utilizar la aplicación.
* `.env.example` — ejemplo de las variables de entorno necesarias.
* `requirements.txt` — dependencias del proyecto.
* `README.md` — documentación e instrucciones de ejecución.

## Requisitos previos

Antes de ejecutar el proyecto se necesita tener instalado:

* Python 3.x
* Microsoft SQL Server
* ODBC Driver para SQL Server
* Git, en caso de clonar el repositorio

También es necesario disponer de una base de datos SQL Server compatible con la estructura utilizada por el proyecto.

## Clonar el repositorio

Repositorio del proyecto:

https://github.com/Candee0623/Zona-Burger.git

Para descargarlo:

git clone https://github.com/Candee0623/Zona-Burger.git

Luego ingresar a la carpeta del proyecto:

cd Zona-Burger

## Crear y activar el entorno virtual

En Windows:

python -m venv venv

Activar el entorno virtual:

venv\Scripts\activate

En Linux o macOS:

python3 -m venv venv

source venv/bin/activate

## Instalar las dependencias

Con el entorno virtual activado, ejecutar:

pip install -r requirements.txt

## Configuración de la base de datos

El proyecto utiliza SQL Server como motor de base de datos.

La configuración se realiza mediante variables de entorno para evitar guardar credenciales directamente en el código fuente.

Copiar el archivo `.env.example` y crear un archivo llamado `.env`:

.env.example → .env

Configurar en `.env` los datos correspondientes a la instancia de SQL Server.

Las variables utilizadas por el proyecto son:

DB_NAME
DB_HOST
DB_PORT
DB_DRIVER
DB_TRUSTED_CONNECTION

Un ejemplo de configuración utilizando autenticación de Windows es:

DB_NAME=ZonaBurger
DB_HOST=localhost
DB_PORT=1433
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_TRUSTED_CONNECTION=yes

Los valores deben adaptarse a la instalación local de SQL Server.

El archivo `.env` contiene información de configuración local y no debe subirse al repositorio.

## Migraciones

Una vez configurada la conexión con SQL Server, ejecutar:

python manage.py migrate

Este comando aplica las migraciones de Django que se encuentran incluidas en el proyecto.

Si las migraciones ya fueron aplicadas, Django mostrará:

No migrations to apply.

## Carga automática de datos iniciales

El proyecto incluye un comando personalizado para evitar que el usuario tenga que ingresar manualmente los datos básicos en la base de datos.

Ejecutar:

python manage.py cargar_datos_iniciales

El comando carga automáticamente los datos iniciales necesarios para el funcionamiento de Zona-Burger.

Entre ellos se encuentran:

### Estados de productos

* Activo
* Oculto
* Eliminado

Los estados utilizan los identificadores requeridos por la aplicación.

### Estados de pedidos

* Pendiente
* En Preparación
* En proceso
* Enviado
* Entregado
* Cancelado

### Medios de pago

* Efectivo
* Transferencia

### Negocio

* Nombre: Zona Burger
* Teléfono: 1152617656

### Zonas de entrega

* Piedra Buena
* Pirelli
* Los Perales
* La Oculta

El comando es seguro de ejecutar nuevamente, ya que verifica la existencia de los datos antes de crearlos.

Por lo tanto, no es necesario realizar inserciones manuales en la base de datos para estos datos iniciales.

## Ejecutar la aplicación

Después de configurar la base de datos y cargar los datos iniciales, ejecutar:

python manage.py runserver

La aplicación estará disponible en:

http://127.0.0.1:8000/

## Accesos principales

### Aplicación

http://127.0.0.1:8000/

Desde aquí se accede a la aplicación principal.

### Panel de administración de Zona-Burger

http://127.0.0.1:8000/panel/

El proyecto cuenta con un panel de administración propio para gestionar la información del negocio.

Este es el panel principal pensado para la administración de Zona-Burger.

### Administración de Django

http://127.0.0.1:8000/admin/

También se encuentra disponible el panel administrativo nativo de Django.

Para acceder a este panel se necesita contar con un usuario administrador.

## Crear un usuario administrador

Si se necesita acceder al administrador nativo de Django, ejecutar:

python manage.py createsuperuser

Luego seguir las instrucciones que aparecen en la consola.

Una vez creado el usuario, se podrá ingresar desde:

http://127.0.0.1:8000/admin/

## Comandos útiles

Verificar que el proyecto no tenga errores:

python manage.py check

Aplicar migraciones:

python manage.py migrate

Cargar los datos iniciales:

python manage.py cargar_datos_iniciales

Crear un usuario administrador:

python manage.py createsuperuser

Iniciar el servidor:

python manage.py runserver

## Secuencia completa de instalación

Para una instalación nueva, la secuencia recomendada es:

1. Clonar el repositorio.
2. Crear el entorno virtual.
3. Activar el entorno virtual.
4. Instalar las dependencias.
5. Configurar el archivo `.env`.
6. Verificar la conexión con SQL Server.
7. Ejecutar las migraciones.
8. Ejecutar el comando `cargar_datos_iniciales`.
9. Iniciar el servidor.
10. Ingresar a la aplicación desde el navegador.

En Windows:

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate

python manage.py cargar_datos_iniciales

python manage.py runserver

## Consideraciones

* No se debe subir el archivo `.env` al repositorio.
* El archivo `.env.example` sirve como plantilla para configurar las variables de entorno.
* Se necesita una instalación funcional de SQL Server.
* También es necesario tener instalado un ODBC Driver compatible con SQL Server.
* El comando `cargar_datos_iniciales` debe ejecutarse después de configurar correctamente la conexión con la base de datos.
* El servidor iniciado mediante `runserver` es únicamente para desarrollo y presentación local.
* No es necesario realizar manualmente las inserciones de los datos iniciales indicados en esta documentación.
