# SIGEA - Sistema Integral de Gestión de Espacios Académicos

Plataforma web para administrar y asignar aulas, laboratorios y espacios académicos. Automatiza el control de horarios y evita empalmes con un **motor de detección de conflictos** que valida cada asignación en el momento de guardarla.

## Características

- **Panel principal:** indicadores de espacios (ocupados, libres y bloqueados), reservas del día, ocupación por edificio y tabla de disponibilidad con filtros y búsqueda por grupo.
- **Asignación de horarios:** asignación de grupos a espacios por periodo, día y bloque horario, con vista de calendario.
- **Motor de prevención de empalmes:** bloquea la asignación si el espacio ya está ocupado ese día y en ese rango de horas, e indica el choque detectado.
- **Reservas especiales:** los usuarios solicitan espacios para eventos; coordinadores y administradores las aprueban o rechazan. Cada solicitud genera una notificación en la interfaz y por correo.
- **Gestión de infraestructura:** catálogo de edificios y espacios (aulas, laboratorios y salas) con su estatus: activo, mantenimiento o inactivo.
- **Gestión de usuarios:** alta, edición y baja de cuentas, restringida a correos del dominio institucional.
- **Interfaz responsiva:** sidebar con iconos SVG, tarjetas y tablas adaptables a móvil.

## Roles y permisos

| Módulo | Administrador | Coordinador | Maestro |
|---|:---:|:---:|:---:|
| Panel principal | ✅ | ✅ | ❌ |
| Asignación de horarios | ✅ | ✅ | Solo consulta |
| Reservas especiales | ✅ (aprueba) | ✅ (aprueba) | Solicita |
| Usuarios | ✅ | ✅ | ❌ |
| Gestión de infraestructura | ✅ | ❌ | ❌ |

## Seguridad
- Contraseñas almacenadas con hash (Werkzeug).
- Protección CSRF en todos los formularios (Flask-WTF).
- Bloqueo temporal por intentos fallidos de inicio de sesión: 5 por correo y 20 por IP en una ventana de 15 minutos.
- Recuperación de contraseña con código de 6 caracteres enviado por correo. Se guarda solo su hash (HMAC-SHA256), vence en 10 minutos, permite 5 intentos y limita los reenvíos (60 s entre envíos y 5 por hora).
- Respuestas genéricas ante correos inexistentes, para no revelar qué cuentas están registradas.
- Cierre de sesión automático por inactividad.
- Registro de errores con rotación de archivos en `logs/sigea.log`.

## Tecnologías
| Capa | Herramientas |
|---|---|
| Backend | Python, Flask, Flask-WTF |
| Base de datos | Microsoft SQL Server, `pyodbc` |
| Frontend | HTML, CSS, JavaScript, Jinja2, SweetAlert2 |
| Correo | SMTP de Gmail (`smtplib`) |

## Equipo de desarrollo: AD astra
| Integrante | Rol |
|---|---|
| **Alex Rangel** | Desarrollo |
| **Diego Guerra** | Desarrollo |

## Licencia
Distribuido bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
