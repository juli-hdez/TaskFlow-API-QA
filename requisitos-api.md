# Requisitos de prueba para la API de Taskflow

**Estado:** API REST implementada para desarrollo local.  
**Versión:** 0.2

## 1. Propósito y alcance

Este documento define requisitos verificables para una API que permita registrar e iniciar sesión, gestionar tareas y consultar el resumen del dashboard de Taskflow. La API está implementada en `api/main.py` con FastAPI y SQLite. El frontend actual sigue guardando sus datos en el navegador y todavía no está conectado a la API.

La API local usa el prefijo `/api/v1`, recibe y devuelve JSON, y requiere un token Bearer en las operaciones privadas. La base de datos de desarrollo se guarda fuera de la carpeta del proyecto, en `%USERPROFILE%\.taskflow\taskflow.db`.

## 2. Modelo de datos propuesto

### Usuario

- `id`: identificador asignado por el servidor.
- `username`: nombre único, entre 3 y 20 caracteres; letras latinas A–Z, números, punto (`.`), guion (`-`) y guion bajo (`_`). No acepta `@`; la comparación no distingue mayúsculas.
- `password`: solo se acepta en solicitudes de registro e inicio de sesión; debe contener al menos 8 letras, 2 números y 1 símbolo permitido entre `.`, `_`, `-` y `@`. No se devuelve en respuestas.

### Tarea

- `id`: identificador asignado por el servidor.
- `title`: obligatorio, entre 1 y 100 caracteres después de quitar espacios al inicio y al final.
- `description`: opcional, hasta 500 caracteres.
- `status`: `pending`, `in-progress` o `completed`.
- `priority`: `low`, `medium` o `high`.
- `dueDate`: fecha opcional con formato `YYYY-MM-DD`.
- `createdAt` y `updatedAt`: marcas de tiempo asignadas por el servidor.

## 3. Requisitos funcionales y criterios de aceptación

| ID | Operación | Criterios de aceptación |
|---|---|---|
| API-01 | Convenciones HTTP | Todas las rutas comienzan con `/api/v1`. Las solicitudes con cuerpo usan `Content-Type: application/json`; las respuestas JSON indican ese tipo de contenido. |
| API-02 | Formato de errores | Las respuestas de error usan un objeto JSON con `error.code` y `error.message`; pueden incluir `error.details` para errores de validación. No incluyen trazas, consultas ni datos internos del servidor. |
| API-03 | Registrar usuario — `POST /api/v1/auth/register` | Con un nombre y contraseña válidos, responde `201 Created` y devuelve el usuario sin contraseña ni hash. Un nombre inválido o contraseña que no cumpla las reglas responde `400 Bad Request`. Un nombre ya registrado, incluso con distinta capitalización, responde `409 Conflict`. |
| API-04 | Iniciar sesión — `POST /api/v1/auth/login` | Con credenciales válidas responde `200 OK` y devuelve `accessToken`, `tokenType: "Bearer"` y `expiresIn: 28800` (8 horas). En esta versión no hay renovación de token. Con nombre o contraseña incorrectos responde `401 Unauthorized` con un mensaje genérico, sin revelar cuál dato falló. |
| API-05 | Cerrar sesión — `POST /api/v1/auth/logout` | Con un token válido responde `204 No Content` e invalida ese token. El mismo token no puede acceder después a rutas protegidas. |
| API-06 | Autenticación de rutas privadas | Las rutas privadas requieren `Authorization: Bearer <token>`. Si falta el token, está mal formado, es inválido, expiró o fue revocado, responden `401 Unauthorized`. |
| API-07 | Crear tarea — `POST /api/v1/tasks` | Con datos válidos responde `201 Created` y devuelve la tarea creada. Si no se especifican `status` o `priority`, usa `pending` y `medium`. El servidor asigna el identificador y las marcas de tiempo. |
| API-08 | Listar y filtrar tareas — `GET /api/v1/tasks` | Devuelve solo las tareas del usuario autenticado, ordenadas por `createdAt` descendente, en `{ "items": [...], "total": n }`. El parámetro opcional `q` busca sin distinguir mayúsculas en título y descripción. El parámetro opcional `status` acepta los tres estados permitidos. Si se envían ambos, se aplican conjuntamente. |
| API-09 | Consultar tarea — `GET /api/v1/tasks/{taskId}` | Si la tarea existe y pertenece al usuario autenticado, responde `200 OK` con sus datos. Si no existe o pertenece a otra cuenta, responde `404 Not Found`. |
| API-10 | Editar tarea — `PATCH /api/v1/tasks/{taskId}` | Permite actualizar uno o más campos editables. Responde `200 OK` con la tarea actualizada; conserva `id` y `createdAt`, y actualiza `updatedAt`. Un campo inválido responde `400 Bad Request`; una tarea inexistente o ajena responde `404 Not Found`. |
| API-11 | Eliminar tarea — `DELETE /api/v1/tasks/{taskId}` | Si la tarea pertenece al usuario autenticado, la elimina y responde `204 No Content`. Una tarea inexistente o ajena responde `404 Not Found`. |
| API-12 | Resumen del dashboard — `GET /api/v1/dashboard/summary` | Devuelve los totales `total`, `inProgress`, `completed` y `overdue` para el usuario autenticado. `overdue` cuenta tareas con `dueDate` anterior a la fecha actual y estado distinto de `completed`. |
| API-13 | Aislamiento entre cuentas | Un usuario no puede listar, consultar, modificar ni eliminar tareas de otra cuenta. Las tareas ajenas se tratan como inexistentes y responden `404 Not Found`. |
| API-14 | Validación de tareas | Títulos vacíos o mayores a 100 caracteres, descripciones mayores a 500, estados o prioridades fuera de catálogo y fechas con formato inválido responden `400 Bad Request`; no se modifica ni crea la tarea. |
| API-15 | Solicitudes mal formadas | JSON inválido responde `400 Bad Request`. Un tipo de contenido no admitido en una solicitud con cuerpo responde `415 Unsupported Media Type`. |

## 4. Requisitos no funcionales de seguridad

| ID | Requisito |
|---|---|
| RNF-API-01 | Las contraseñas se almacenan con un algoritmo de hash seguro del lado del servidor; nunca se guardan ni se registran en texto plano. |
| RNF-API-02 | Las respuestas de registro, inicio de sesión, tareas y errores nunca exponen contraseñas, hashes, tokens de otros usuarios ni secretos internos. |
| RNF-API-03 | Las solicitudes y respuestas no deben revelar si un nombre de usuario existe durante un inicio de sesión fallido. |
| RNF-API-04 | El entorno desplegado debe usar HTTPS. Las pruebas locales pueden usar HTTP solo en un entorno de desarrollo aislado. |

## 5. Alcance pendiente de decisión

Antes de ampliar o publicar la API se deben confirmar, como mínimo:

- Política CORS para los orígenes permitidos.
- Límites de solicitudes y criterios de rendimiento.
- Si se requiere paginación para `GET /api/v1/tasks`.

## 6. Fuera del alcance de esta propuesta

- Recuperación de contraseña, verificación de identidad o eliminación de cuenta.
- Compartir tareas, equipos, roles o permisos.
- Notificaciones externas y sincronización con servicios de terceros.
