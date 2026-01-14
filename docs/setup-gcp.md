# Guía de Configuración de Google Cloud Platform (GCP) para LifeOS

Esta guía describe los pasos necesarios para configurar los servicios de GCP requeridos por LifeOS, específicamente Firestore y la autenticación mediante una cuenta de servicio.

## 1. Habilitar la API de Firestore

Firestore se utiliza como backend para la gestión de memoria persistente (sesiones y memoria a largo plazo).

1.  **Ve a la consola de GCP:** Accede a [https://console.cloud.google.com/](https://console.cloud.google.com/).
2.  **Selecciona tu proyecto:** Asegúrate de tener seleccionado el proyecto correcto en la parte superior de la consola.
3.  **Habilita la API:**
    *   En el menú de navegación, ve a **APIs y servicios > Biblioteca**.
    *   Busca "Cloud Firestore API".
    *   Selecciónala y haz clic en **Habilitar**.
4.  **Crea una base de datos Firestore:**
    *   Una vez habilitada la API, ve a la sección de **Firestore** en el menú de navegación.
    *   Haz clic en **Crear base de datos**.
    *   Elige el modo **Nativo** (Native Mode).
    *   Selecciona una ubicación cercana a tus usuarios (ej. `europe-west1`).
    *   Haz clic en **Crear**.

## 2. Crear una Cuenta de Servicio (Service Account)

Una cuenta de servicio permite que la aplicación se autentique con los servicios de GCP de forma segura sin necesidad de usar credenciales de usuario personales.

1.  **Ve a IAM y Administración:** En el menú de navegación, ve a **IAM y administración > Cuentas de servicio**.
2.  **Crea la cuenta:**
    *   Haz clic en **+ CREAR CUENTA DE SERVICIO**.
    *   **Nombre de la cuenta de servicio:** `lifeos-firestore-sa` (o un nombre descriptivo).
    *   **ID de cuenta de servicio:** Se generará automáticamente.
    *   **Descripción:** "Cuenta de servicio para que LifeOS acceda a Firestore".
    *   Haz clic en **CREAR Y CONTINUAR**.
3.  **Asigna roles:**
    *   En la sección "Conceder a esta cuenta de servicio acceso al proyecto", busca y añade el siguiente rol:
        *   `Cloud Datastore User` (Este rol proporciona permisos completos para Firestore en modo nativo).
    *   Haz clic en **CONTINUAR**.
4.  **Genera la clave (JSON):**
    *   En el último paso ("Conceder a los usuarios acceso a esta cuenta de servicio"), puedes omitirlo y hacer clic en **HECHO**.
    *   Busca la cuenta recién creada en la lista, haz clic en los tres puntos (Acciones) y selecciona **Administrar claves**.
    *   Haz clic en **AÑADIR CLAVE > Crear nueva clave**.
    *   Selecciona **JSON** como tipo de clave y haz clic en **CREAR**.
    *   Se descargará un archivo JSON. **Renómbralo a `credentials.json`** y guárdalo en un lugar seguro. **¡No lo subas al repositorio de Git!**

## 3. Configuración Local para Pruebas con Firestore

Para que tu entorno de desarrollo local pueda conectarse a Firestore usando las credenciales que acabas de crear, necesitas "montarlas" para que la aplicación las encuentre.

La forma estándar es usando la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS`.

### Opción A: Usando `docker-compose.yml` (Recomendado)

> **[WIP]** Esta sección está pendiente de ser actualizada. La inyección de credenciales se gestionará a través de secretos de Docker o una solución similar en el futuro.

Por ahora, utiliza la "Opción B" para desarrollo local.


### Opción B: Ejecución Local (sin Docker)

Si ejecutas el script `main.py` directamente en tu máquina:

1.  **Coloca `credentials.json`** en la raíz del proyecto.
2.  **Establece la variable de entorno** en tu terminal antes de ejecutar el script.

    **En Windows (PowerShell):**
    ```powershell
    $env:GOOGLE_APPLICATION_CREDENTIALS="c:\ruta\completa\a\tu\proyecto\lifeOS\credentials.json"
    python main.py
    ```

    **En macOS/Linux:**
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="/ruta/completa/a/tu/proyecto/lifeOS/credentials.json"
    python main.py
    ```
Esta variable solo persistirá durante la sesión de tu terminal. Para hacerla permanente, deberás añadirla a tu perfil de shell (`.bashrc`, `.zshrc`, etc.) o a las variables de entorno del sistema.
