# Agente de ventas

Agente que responde en lenguaje natural sobre `sales_data.db`, una base SQLite
con ventas de supermercado. Tiene dos formas de usarse: un CLI y una interfaz
web. Está construido sobre la sección **Agente simple de ventas** de
`original.ipynb`, con el SDK de Copilot y OpenRouter.

Repositorio: <https://github.com/yogoni/agente-ventas>
Basado en el repositorio original del curso: <https://github.com/juananpe/agente-ventas>

## Arranque rápido en GitHub Codespaces

1. En la página del repositorio, **Code → Codespaces → Create codespace on main**.
2. Espera a que termine la preparación del contenedor: instala las dependencias y
   predescarga el runtime del SDK.
3. Abre `.env` y pega tu clave de OpenRouter. El contenedor crea el fichero a
   partir de `.env.example`, con el valor vacío:

   ```
   OPENROUTER_API_KEY=tu_clave
   ```

   Puedes crear una clave en <https://openrouter.ai/keys>. `.env` está excluido
   de Git, así que tu clave no se sube al repositorio.

4. Arranca la aplicación (dentro del contenedor no se usa `.venv`, y hay que
   escuchar en todas las interfaces para que funcione el reenvío de puertos):

   ```sh
   python -m uvicorn web_app:app --host 0.0.0.0 --port 8000
   ```

5. Abre el puerto: pestaña **Ports** del panel inferior → icono del globo
   terráqueo del puerto 8000. La URL tiene la forma
   `https://<codespace>-8000.app.github.dev`. Por defecto el puerto es privado
   (solo tú); para abrirlo a otros dispositivos, clic derecho sobre 8000 →
   **Port Visibility** → **Public**.

## Arranque en local con Dev Containers

Solo necesitas [Docker](https://www.docker.com/products/docker-desktop/) y
[Visual Studio Code](https://code.visualstudio.com/) con la extensión **Dev
Containers**. Da igual el sistema operativo.

1. Clona el repositorio:

   ```sh
   git clone https://github.com/yogoni/agente-ventas.git
   ```

2. Abre esa carpeta en VS Code y elige **Reopen in Container**
   (`F1` → `Dev Containers: Reopen in Container`).

3. Pega tu clave en `.env`, igual que en el apartado anterior.

4. Ejecuta lo que quieras:

   ```sh
   python -m uvicorn web_app:app --host 0.0.0.0 --port 8000   # interfaz web
   python agente_ventas.py                                      # CLI interactivo
   ```

Dentro del contenedor `python` ya apunta al entorno correcto: no hay que activar
nada ni usar rutas con `.venv`.

## Arranque sin Docker

Necesitas Python 3.11 o posterior. Desde la carpeta del repositorio:

macOS y Linux:

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env        # y pega tu clave en .env
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

### Agente de línea de comandos

macOS y Linux:

```sh
./.venv/bin/python agente_ventas.py
```

Windows (PowerShell):

```powershell
.venv\Scripts\python agente_ventas.py
```

También admite una pregunta única:

```sh
./.venv/bin/python agente_ventas.py --pregunta "¿Cuál es el top 5 de tiendas por ventas totales?"
```

En el modo interactivo, escribe `salir` para terminar.

### Aplicación web

`web_app.py` sirve la interfaz de `static/` (HTML, CSS y JavaScript sin
frameworks) con FastAPI.

macOS y Linux:

```sh
./.venv/bin/python -m uvicorn web_app:app --host 127.0.0.1 --port 8000
```

Windows (PowerShell):

```powershell
.venv\Scripts\python -m uvicorn web_app:app --host 127.0.0.1 --port 8000
```

Abre <http://127.0.0.1:8000>.

Ejecuta los comandos **desde la carpeta del repositorio**: las rutas
`.venv\Scripts\...` son relativas, y desde otra carpeta PowerShell se queja de
que «el módulo '.venv' no pudo cargarse».

Cada conversación mantiene su contexto en una sesión del agente en memoria del
servidor; el botón "Nueva conversación" la elimina y las sesiones se pierden al
reiniciar el proceso. Se admiten como máximo 100 conversaciones simultáneas.

## Detalles

Usa OpenRouter con el modelo `deepseek/deepseek-v4.1-flash`; puedes elegir otro
con `--modelo ID_DEL_MODELO`.

La clave se lee de `.env` al arrancar. Si `OPENROUTER_API_KEY` ya está definida
en el entorno, también la usa.

El SDK descarga su runtime nativo en el primer arranque (los contenedores de
desarrollo ya lo traen predescargado), así que la primera petición puede tardar
un poco más.

La base SQLite se abre en modo de solo lectura y se devuelven como máximo 100
filas por consulta.
