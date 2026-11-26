# Requisitos de Taskflow

## 1. Propósito

Taskflow es una aplicación web de demostración para que una persona gestione sus tareas y practique el diseño y la ejecución de pruebas de software.

## 2. Alcance y supuestos

- El frontend actual funciona en el navegador y todavía no está conectado a la API.
- El frontend guarda sus cuentas y tareas en el almacenamiento local del navegador.
- Hay una API REST independiente para desarrollo local, implementada con FastAPI y SQLite; sus datos no se sincronizan con los del frontend.
- La autenticación local del frontend y de la API es demostrativa y no sustituye un sistema de producción.
- Cada cuenta ve únicamente las tareas asociadas a su nombre de usuario dentro de ese navegador.
- Las cuentas locales del frontend creadas con la versión anterior (basada en correo) no se migran; se debe crear una cuenta nueva. Los datos anteriores no se eliminan automáticamente.

## 3. Requisitos funcionales

| ID | Requisito | Criterios de aceptación |
|---|---|---|
| RF-01 | Registro de cuenta | La persona puede registrarse con un nombre de usuario obligatorio de 3–20 caracteres: letras latinas A–Z, números, punto (`.`), guion (`-`) y guion bajo (`_`). No se permite `@`. El nombre se normaliza a minúsculas y debe ser único sin distinguir mayúsculas. La contraseña debe contener al menos 8 letras, 2 números y 1 carácter especial entre `.`, `_`, `-` y `@` (mínimo 11 caracteres en total); no se permiten otros caracteres. Se solicita confirmar la contraseña. Si el usuario no es válido, está en uso, la contraseña no cumple las reglas o la confirmación no coincide, se muestra respectivamente: «Lo sentimos, nombre de usuario no válido», «Lo sentimos, este nombre de usuario ya está en uso», «Lo sentimos, tu contraseña no cumple con los parámetros solicitados» o «Lo sentimos, las contraseñas no concuerdan». Al completar el registro, inicia sesión. |
| RF-02 | Inicio de sesión | La persona puede iniciar sesión con un nombre de usuario registrado y su contraseña correcta, cumpliendo las reglas de caracteres y composición. Si el nombre o la contraseña no coinciden, se muestra un mensaje de error y no se abre el dashboard. |
| RF-03 | Cierre de sesión | Al cerrar sesión, se elimina la sesión activa y se vuelve a la pantalla de acceso. |
| RF-04 | Crear tarea | La persona puede crear una tarea con título obligatorio (máximo 100 caracteres) y descripción opcional (máximo 500), usando únicamente letras del alfabeto latino, espacios, coma, punto y coma o punto. Puede indicar una fecha límite opcional, solo numérica y no anterior a la fecha de creación de la tarea. Por defecto, el estado inicial es «Pendiente» y la prioridad inicial es «Media». |
| RF-05 | Editar tarea | La persona puede cambiar el título, descripción, estado, prioridad o fecha límite de una tarea existente. Los cambios se reflejan en la lista y el dashboard. |
| RF-06 | Eliminar tarea | Antes de eliminar una tarea, el sistema solicita confirmación. Si se confirma, la tarea desaparece de la lista y los indicadores se actualizan; si se cancela, la tarea se conserva. |
| RF-07 | Consultar tareas | La lista muestra las tareas de la cuenta activa, con título, estado y prioridad; muestra también la descripción y fecha límite cuando existen. Las más recientes aparecen primero. |
| RF-08 | Buscar tareas | La persona puede buscar por texto en el título o la descripción. La búsqueda no distingue mayúsculas de minúsculas y puede combinarse con el filtro de estado. |
| RF-09 | Filtrar por estado | La persona puede ver todas las tareas o limitar la lista a «Pendiente», «En progreso» o «Completada». |
| RF-10 | Consultar dashboard | El dashboard muestra el total de tareas, las tareas «En progreso», las completadas y las vencidas. Una tarea está vencida si su fecha límite es anterior al día actual y su estado no es «Completada». |
| RF-11 | Conservar datos | Las cuentas y tareas permanecen guardadas al recargar la página en el mismo navegador. Las tareas de cada cuenta se almacenan por separado usando el nombre de usuario. La sesión se conserva durante la sesión de la pestaña actual y se elimina al cerrar sesión. |

## 4. Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-01 | La interfaz debe adaptarse a pantallas de escritorio y móviles. |
| RNF-02 | Los controles deben tener etiquetas comprensibles y un indicador de foco visible al navegar con teclado. Los mensajes de error, confirmación y estados vacíos deben ser visibles. |
| RNF-03 | La aplicación debe funcionar en navegadores modernos con soporte para Web Crypto, `localStorage`, `sessionStorage` y el elemento HTML `dialog`. |
| RNF-04 | Las contraseñas no deben guardarse en texto plano; la demo guarda un hash con salt en el almacenamiento local. Estos datos siguen siendo accesibles desde el navegador del usuario, por lo que la solución no debe considerarse segura para cuentas reales. |
| RNF-05 | Las operaciones de gestión de tareas y persistencia no deben requerir conexión a un servicio remoto. |
| RNF-06 | La interfaz debe respetar la preferencia del sistema para reducir el movimiento y las animaciones. |

## 5. Fuera del alcance actual

- Backend, base de datos remota o sincronización entre dispositivos.
- Restablecimiento de contraseña o administración de cuentas.
- Compartir tareas, equipos, roles o permisos.
- Notificaciones externas o recordatorios automáticos.

## 6. Criterio de aceptación general

La versión se considera aceptable cuando una persona puede crear una cuenta local, iniciar y cerrar sesión, gestionar tareas, buscarlas y filtrarlas, consultar los indicadores del dashboard y conservar sus datos al recargar la página en el mismo navegador.
