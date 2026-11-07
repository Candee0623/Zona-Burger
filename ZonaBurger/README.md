# Zona Burger

Aplicación web desarrollada con **Django y PostgreSQL** para gestionar productos, stock, clientes, pedidos y promociones. Incluye la tienda para los clientes y un panel interno para el negocio.

## Tecnologías

- Django 6.1 y PostgreSQL.
- Gunicorn y WhiteNoise (servidor y archivos estáticos en producción).
- Cloudinary (almacenamiento de imágenes de productos).
- Jazzmin (administración de Django) y CKEditor 5.
- Publicación en **Render** (servicio web + base PostgreSQL).

## Requisitos para trabajar en tu computadora

- Python 3.13 de 64 bits.
- Git y VS Code.
- PostgreSQL 14 o superior (con pgAdmin, que se instala junto con PostgreSQL).
- Una cuenta gratuita de [Cloudinary](https://cloudinary.com/), solo si se van a subir imágenes de productos.

## 1. Descargar el proyecto

```powershell
git clone https://github.com/Candee0623/Zona-Burger.git
```

```powershell
cd Zona-Burger
```

Abrir esa carpeta en VS Code. Ejecutar los siguientes comandos desde la carpeta donde está `manage.py`, uno por uno.

## 2. Instalar las dependencias

```powershell
py -3.13 -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Estos comandos usan directamente el entorno virtual; no es necesario activarlo.

## 3. Crear la base de datos local

Con **pgAdmin**: clic derecho sobre *Databases* → *Create* → *Database* y llamarla `zonaburger`.

O desde la terminal (si `psql` está en el PATH):

```powershell
psql -U postgres -c "CREATE DATABASE zonaburger;"
```

La base queda vacía: las tablas se crean en el paso 5.

## 4. Crear el archivo .env

Crear `.env` junto a `manage.py` con este contenido:

```dotenv
SECRET_KEY=una-clave-solo-para-pruebas-locales
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgres://postgres:TU_CONTRASEÑA@localhost:5432/zonaburger

# Solo para subir imágenes (datos de tu cuenta de Cloudinary)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Reemplazar `TU_CONTRASEÑA` por la contraseña de PostgreSQL. Si tiene símbolos como `@`, `#` o `/`, hay que escribirlos codificados (`@` → `%40`, `#` → `%23`, `/` → `%2F`).

Los correos (recuperar contraseña) se muestran en la terminal mientras no se configure un envío real. Para enviarlos de verdad con Gmail, agregar:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST_USER=tu-correo@gmail.com
EMAIL_HOST_PASSWORD=contraseña-de-aplicación
DEFAULT_FROM_EMAIL=Zona Burger <tu-correo@gmail.com>
```

> Las variables `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_DRIVER` y `DB_TRUSTED_CONNECTION` de versiones anteriores (SQL Server) **ya no se usan**: se pueden borrar del `.env`.

**No subir `.env` a GitHub.** Ya está incluido en `.gitignore`.

## 5. Verificar y crear las tablas

```powershell
.\.venv\Scripts\python.exe manage.py check
```

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

`migrate` crea todas las tablas desde cero. No hace falta importar ningún archivo SQL.

## 6. Cargar datos iniciales y permisos

```powershell
.\.venv\Scripts\python.exe manage.py cargar_datos_iniciales
```

```powershell
.\.venv\Scripts\python.exe manage.py sync_permisos
```

La carga inicial agrega:

- Estados de productos y pedidos.
- Medios de pago.
- Datos del negocio.
- Zonas de entrega.

`sync_permisos` crea o actualiza los permisos del sistema que se asignan a los roles. Ambos comandos se pueden repetir sin duplicar datos.

**No agregan productos ni categorías:** se cargan después desde el panel. Pueden actualizar algunos datos existentes del negocio y las zonas.

## 7. Crear un administrador

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Seguir las instrucciones de usuario, correo y contraseña. Al escribir la contraseña no se muestran caracteres; es normal. Con este usuario se puede ingresar al panel y a la administración de Django. El resto de los empleados se crean desde la sección *Empleados* del panel.

## 8. Ejecutar la aplicación

```powershell
.\.venv\Scripts\python.exe manage.py runserver 8002
```

| Acceso | Dirección |
| --- | --- |
| Aplicación | [Página principal](http://127.0.0.1:8002/) |
| Panel de Zona Burger | [Panel](http://127.0.0.1:8002/panel/) |
| Administración de Django | [Administrador](http://127.0.0.1:8002/admin/) |

Dejar la terminal abierta. Para detener el servidor, presionar **Ctrl + C**. En las próximas sesiones solo hace falta iniciar el servidor.

## 9. Ejecutar las pruebas

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## Publicar en Render

### 1. Base de datos

En Render: **New → PostgreSQL**. Cuando esté lista, copiar dos direcciones de su página:

- **Internal Database URL**: la usa el servicio web (misma región, más rápida y segura).
- **External Database URL**: solo para ejecutar comandos desde tu computadora (ver el punto 4).

### 2. Servicio web

En Render: **New → Web Service**, conectado al repositorio de GitHub.

| Campo | Valor |
| --- | --- |
| Build Command | `bash build.sh` |
| Start Command | `gunicorn ZonaBurger.wsgi:application` |

`build.sh` instala las dependencias, recopila los archivos estáticos (`collectstatic`) y aplica las migraciones (`migrate`) en cada publicación. Usar `bash build.sh` (y no `./build.sh`) evita errores de permisos del archivo.

### 3. Variables de entorno

| Variable | Valor |
| --- | --- |
| `SECRET_KEY` | Una clave larga y aleatoria, **distinta** a la de tu computadora |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `tu-app.onrender.com,zonaburger.com.ar,www.zonaburger.com.ar` |
| `DATABASE_URL` | La **Internal Database URL** de la base |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Datos de la cuenta de Cloudinary |
| `EMAIL_BACKEND`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Solo si se quieren enviar correos reales |

Para generar una `SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Si `ALLOWED_HOSTS` está definido, hay que incluir en la lista la dirección de Render y el dominio propio. Los dominios con HTTPS también deben figurar en `CSRF_TRUSTED_ORIGINS` (en `ZonaBurger/settings.py`).

### 4. Primera puesta en marcha

Después del primer despliegue, la base tiene las tablas pero está vacía. Cargar los datos iniciales y crear el administrador. Si tu plan de Render incluye **Shell**, ejecutar ahí los tres comandos. Si no, hacerlo desde tu computadora apuntando a la base de Render (reemplazar por la **External Database URL**):

```powershell
$env:DATABASE_URL = "pegar-aquí-la-External-Database-URL"
.\.venv\Scripts\python.exe manage.py cargar_datos_iniciales
.\.venv\Scripts\python.exe manage.py sync_permisos
.\.venv\Scripts\python.exe manage.py createsuperuser
Remove-Item Env:DATABASE_URL
```

Esto se hace una sola vez. La última línea quita la variable para no seguir apuntando a producción por error.

### Seguridad en producción

Con `DEBUG=False`, `ZonaBurger/settings.py` activa automáticamente:

| Ajuste | Para qué sirve |
| --- | --- |
| `SECURE_PROXY_SSL_HEADER` | Render maneja el HTTPS en su proxy y avisa a Django con un encabezado. Sin esto Django cree que todo llega por HTTP y entra en un bucle de redirecciones. |
| `SECURE_SSL_REDIRECT` | Redirige `http://` a `https://`, para que nadie escriba su contraseña sin cifrar. |
| `SESSION_COOKIE_SECURE` | La cookie de sesión (la que mantiene el login) solo viaja por HTTPS. |
| `CSRF_COOKIE_SECURE` | Lo mismo para la cookie que protege los formularios de ataques CSRF. |
| `SECURE_HSTS_SECONDS` | Indica al navegador que use siempre HTTPS con el sitio. Está en 1 hora; cuando todo funcione bien, subirlo a `31536000` (1 año). |

Además, la conexión a la base exige SSL solo cuando `DEBUG=False`. Con `DEBUG=True` (en tu computadora) estos ajustes no se activan.

> **No probar en tu computadora con `DEBUG=False`**: redirige a HTTPS y `localhost` deja de funcionar.

## Actualizar el proyecto

**En tu computadora**, detener el servidor. Si `git status --short` no muestra cambios propios, ejecutar:

```powershell
git pull --ff-only
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe manage.py check
```

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

**En Render**, alcanza con subir los cambios a GitHub (`git push`): se vuelve a publicar solo y `build.sh` aplica las migraciones pendientes.

## Convenciones de la interfaz

El sitio no usa los cuadros de diálogo del navegador; todo tiene el estilo de Zona Burger.

- **Confirmaciones:** no usar `confirm()` ni `alert()`. Agregar `data-confirmar` al botón, enlace o formulario:

  ```html
  <form method="post" action="..."
        data-confirmar="¿Seguro que deseas eliminar este rol?"
        data-confirmar-titulo="Eliminar rol"
        data-confirmar-boton="Eliminar"
        data-confirmar-tipo="peligro">
  ```

  Desde JavaScript: `await ZB.confirmar({ titulo, mensaje, textoConfirmar, tipo })` y `ZB.avisar({ titulo, mensaje })`. Los archivos son `core/static/js/components/dialogos.js` y `core/static/css/components/dialogos.css`; se cargan en `panel/base.html` y en las pantallas de ingreso.
- **Avisos de formulario:** los mensajes de campos obligatorios o inválidos también usan el estilo propio (en español) en lugar del cartel del navegador.
- **Campos numéricos:** los `<input type="number">` del panel se muestran con formato argentino (`12.000`, `1.500,50`), no cambian al usar la rueda del mouse y envían al servidor el número sin formato. La lógica está en `core/static/js/panel/panel.js`.

## Estructura del proyecto

- `ZonaBurger/`: configuración de Django (`settings.py`, `urls.py`, `wsgi.py`).
- `core/`: la aplicación (modelos, vistas, pruebas).
  - `core/templates/panel/` y `core/static/*/panel/`: panel interno.
  - `core/templates/publico/` y `core/static/*/publico/`: tienda para clientes.
  - `core/management/commands/`: comandos propios (`cargar_datos_iniciales`, `sync_permisos`, `cargar_pedidos_ejemplo`).
- `build.sh` y `Procfile`: publicación en Render.
- `requirements.txt`: dependencias de Python.

## Problemas frecuentes

| Síntoma | Causa y solución |
| --- | --- |
| `DisallowedHost` | Falta el dominio en `ALLOWED_HOSTS`. |
| `CSRF verification failed` | El dominio no está en `CSRF_TRUSTED_ORIGINS` (`settings.py`). |
| `server does not support SSL` en tu computadora | Verificar que el `.env` tenga `DEBUG=True`. |
| Las imágenes de productos no se suben | Faltan las variables `CLOUDINARY_*`. |
| La página se ve sin estilos en Render | Revisar que el Build Command sea `bash build.sh` y que `collectstatic` no haya fallado. |
| Error de permisos al ejecutar el build | Usar `bash build.sh` como Build Command. |
