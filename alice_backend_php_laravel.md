# Banco de preguntas — Entrevista técnica Backend PHP/Laravel

## Pregunta 1: Principios SOLID
¿Qué son los principios SOLID y puedes dar un ejemplo de cómo aplicarías el Principio de Responsabilidad Única (SRP) en una clase de Laravel, por ejemplo un Controller que actualmente hace demasiadas cosas?

**Puntos clave a evaluar:**
- Menciona los 5 principios (al menos reconoce que existen: SRP, OCP, LSP, ISP, DIP)
- Explica SRP correctamente: una clase debe tener una única razón para cambiar
- Da un ejemplo concreto (ej. mover lógica de negocio de un Controller a un Service o Action class)
- Bonus: menciona que esto facilita testing y mantenimiento

---

## Pregunta 2: PSR (PHP Standards Recommendations)
¿Qué es un PSR y puedes mencionar para qué sirven el PSR-4 y el PSR-12?

**Puntos clave a evaluar:**
- Explica que PSR son estándares de la comunidad PHP-FIG para interoperabilidad y consistencia
- PSR-4: autoloading de clases basado en namespaces (mapea namespace a estructura de directorios)
- PSR-12: estilo de código (formato, indentación, convenciones de nombres)
- Bonus: menciona que Composer usa PSR-4 para el autoload

---

## Pregunta 3: Problema N+1 en Eloquent
¿Qué es el problema de consultas N+1 en Eloquent? Descríbelo con un ejemplo y explica cómo lo solucionarías.

**Puntos clave a evaluar:**
- Explica que ocurre al iterar una colección y acceder a una relación sin haberla cargado antes, generando una query extra por cada registro
- Da un ejemplo (ej. `foreach ($posts as $post) { $post->author->name }` sin eager loading)
- Menciona la solución: eager loading con `with()`, ej. `Post::with('author')->get()`
- Bonus: menciona herramientas para detectarlo (Laravel Debugbar, Telescope, o el paquete `beyondcode/laravel-query-detector`)

---

## Pregunta 4: Mass Assignment
¿Qué es "mass assignment" en Laravel y por qué puede ser un riesgo de seguridad? ¿Cómo te proteges de eso?

**Puntos clave a evaluar:**
- Explica que es asignar múltiples atributos a un modelo de una sola vez, típicamente con `Model::create($request->all())`
- Identifica el riesgo: un atacante podría inyectar campos no esperados (ej. `is_admin = true`) si no se controla
- Menciona las soluciones: `$fillable` (whitelist de campos permitidos) o `$guarded` (blacklist), y usar Form Requests con validación explícita en vez de `$request->all()`
- Bonus: menciona que `$guarded = []` sin `$fillable` es peligroso

---

## Pregunta 5: Migraciones
¿Qué son las migraciones en Laravel y por qué son una buena práctica frente a modificar la base de datos directamente? ¿Qué pasa si necesitas revertir un cambio?

**Puntos clave a evaluar:**
- Explica que son un control de versiones para el esquema de la base de datos, escrito en código PHP
- Menciona ventajas: reproducibilidad entre entornos (desarrollo, producción, entre miembros del equipo), historial de cambios
- Explica el método `down()` para revertir (`php artisan migrate:rollback`)
- Bonus: menciona buenas prácticas como no editar una migración ya ejecutada en producción, sino crear una nueva

---

## Pregunta 6: Eloquent vs Query Builder
¿Cuándo usarías Eloquent y cuándo el Query Builder directo en Laravel? ¿Qué ventajas y desventajas tiene cada uno?

**Puntos clave a evaluar:**
- Eloquent: ORM orientado a objetos, más legible, maneja relaciones, eventos de modelo, accessors/mutators — pero tiene más overhead de rendimiento
- Query Builder: más cercano a SQL, más rápido para consultas complejas o reportes pesados, sin la sobrecarga de hidratar modelos completos
- Da un criterio razonable de cuándo usar cada uno (ej. CRUD normal → Eloquent; reportes/agregaciones pesadas → Query Builder o consultas raw)
- Bonus: menciona que ambos comparten la misma capa de conexión a base de datos

---

## Pregunta 7: Validación de datos
¿Cómo validas los datos de entrada en Laravel? ¿Por qué es mala práctica confiar solo en la validación del frontend?

**Puntos clave a evaluar:**
- Menciona Form Requests (`php artisan make:request`) como la forma recomendada de validación estructurada
- También puede mencionar `$request->validate([...])` directo en el controller para casos simples
- Explica que el frontend puede ser manipulado (deshabilitar JS, llamadas directas a la API), por lo que la validación del servidor es obligatoria, no opcional
- Bonus: menciona reglas de validación custom o el uso de `Rule` classes

---

## Pregunta 8: Middleware
¿Qué es un middleware en Laravel? Da un ejemplo de un caso de uso real donde lo aplicarías.

**Puntos clave a evaluar:**
- Explica que es una capa que filtra/procesa las peticiones HTTP antes o después de que lleguen al controller
- Da un ejemplo correcto (autenticación, verificar rol/permiso, logging, CORS, rate limiting)
- Menciona cómo se registra (en rutas, grupo de rutas, o kernel)
- Bonus: distingue entre middleware "antes" y "después" de la petición

---

## Pregunta 9: Inyección de dependencias y Service Container
¿Qué es la inyección de dependencias y cómo la resuelve Laravel a través de su Service Container?

**Puntos clave a evaluar:**
- Explica el concepto general: en vez de que una clase cree sus propias dependencias, se las "inyectan" desde afuera (constructor o método)
- Menciona que Laravel resuelve automáticamente las dependencias con type-hinting en constructores o métodos de controller
- Puede mencionar bindings manuales en un Service Provider cuando se necesita resolver una interfaz a una implementación específica
- Bonus: explica la ventaja para testing (poder inyectar mocks/fakes)

---

## Pregunta 10: Manejo de errores y excepciones
¿Cómo maneja Laravel las excepciones por defecto, y cómo personalizarías el manejo de errores para una API REST?

**Puntos clave a evaluar:**
- Menciona el manejador de excepciones central (Handler.php en versiones anteriores, o el approach de `bootstrap/app.php` en Laravel 11+)
- Explica que para una API se deben devolver respuestas JSON consistentes con códigos de estado HTTP apropiados (400, 404, 422, 500)
- Menciona el uso de excepciones personalizadas para casos de negocio específicos
- Bonus: menciona logging de errores (Log facade, servicios como Sentry)

---

## Pregunta 11: Colas (Queues) y trabajos en segundo plano
¿Para qué sirven las colas (queues) en Laravel? Da un ejemplo de cuándo las usarías en vez de procesar algo de forma síncrona.

**Puntos clave a evaluar:**
- Explica que permiten diferir tareas pesadas o lentas para que no bloqueen la respuesta al usuario
- Da un ejemplo correcto (envío de correos, generación de reportes, procesamiento de imágenes, notificaciones)
- Menciona el concepto de "Jobs" y un worker que los procesa (`php artisan queue:work`)
- Bonus: menciona drivers de cola (database, Redis) o el manejo de reintentos ante fallos

---

## Pregunta 12: Testing en Laravel
¿Qué tipos de pruebas conoces en el contexto de Laravel (unitarias, de características/feature) y cuál es la diferencia entre ellas?

**Puntos clave a evaluar:**
- Distingue pruebas unitarias (prueban una clase/método aislado, sin dependencias externas) de pruebas de característica/feature (prueban un flujo completo, ej. una petición HTTP a una ruta)
- Menciona PHPUnit o Pest como herramientas usadas en Laravel
- Da un ejemplo de qué probaría con cada tipo
- Bonus: menciona el uso de factories y seeders para preparar datos de prueba, o el uso de mocks/fakes

---

## Pregunta 13: Composer y gestión de dependencias
¿Qué es Composer y qué diferencia hay entre el archivo `composer.json` y `composer.lock`?

**Puntos clave a evaluar:**
- Explica que Composer es el gestor de dependencias de PHP, similar a npm en JavaScript
- `composer.json`: declara las dependencias del proyecto y sus rangos de versión permitidos
- `composer.lock`: fija las versiones exactas instaladas, para que todos los entornos usen las mismas versiones
- Bonus: menciona que `composer.lock` debe subirse al control de versiones para reproducibilidad entre entornos

---

## Pregunta 14: Blade Templating
¿Qué es Blade en Laravel? Menciona alguna directiva que uses seguido y para qué sirve.

**Puntos clave a evaluar:**
- Explica que Blade es el motor de plantillas de Laravel, permite mezclar HTML con lógica PHP de forma más limpia
- Menciona directivas comunes (`@if`, `@foreach`, `@extends`, `@section`, `@include`, `@component`)
- Explica el concepto de layouts (plantilla base que se extiende en otras vistas)
- Bonus: menciona que Blade compila a PHP plano y cachea el resultado para rendimiento

---

## Pregunta 15: Rutas y Route Model Binding
¿Qué es el Route Model Binding en Laravel? Da un ejemplo de cómo simplifica el código de un controller.

**Puntos clave a evaluar:**
- Explica que permite inyectar automáticamente una instancia de modelo en un método del controller, basándose en el parámetro de la ruta (ej. el ID en la URL)
- Da un ejemplo (ej. en vez de buscar manualmente `Post::find($id)`, Laravel resuelve el modelo directo si el parámetro de la ruta coincide con el nombre de la variable tipada en el método)
- Menciona que si el modelo no existe, Laravel devuelve automáticamente un error 404
- Bonus: menciona el binding implícito vs explícito (definido en el Service Provider)

---

## Pregunta 16: API Resources
¿Qué son los API Resources en Laravel y para qué se usan al construir una API?

**Puntos clave a evaluar:**
- Explica que son clases que transforman modelos o colecciones de modelos en una estructura JSON controlada, antes de devolverlos como respuesta
- Menciona la ventaja: separa la estructura de la base de datos de la estructura que expone la API (no todos los campos del modelo tienen que salir en la respuesta)
- Da un ejemplo de uso (ej. ocultar campos sensibles, renombrar campos, agregar datos calculados)
- Bonus: menciona Resource Collections para transformar listas completas

---

## Pregunta 17: Autenticación con Sanctum o Passport
¿Qué opciones conoces para manejar autenticación de APIs en Laravel? ¿Cuál usarías para una API consumida por una app móvil o un frontend separado (SPA)?

**Puntos clave a evaluar:**
- Menciona Laravel Sanctum como opción ligera para autenticación de SPAs y APIs simples basadas en tokens
- Menciona Laravel Passport como opción más completa, orientada a implementar OAuth2
- Da un criterio razonable de cuándo usar cada uno (Sanctum para casos simples, Passport cuando se necesita el estándar OAuth2 completo, por ejemplo dar acceso a aplicaciones de terceros)
- Bonus: menciona el concepto de token de acceso (access token) y su envío en el header de autorización

---

## Pregunta 18: Autorización con Policies y Gates
¿Cuál es la diferencia entre una Policy y un Gate en Laravel? Da un ejemplo de cuándo usarías cada uno.

**Puntos clave a evaluar:**
- Explica que ambos sirven para definir reglas de autorización (qué puede o no hacer un usuario)
- Gates: closures simples, útiles para acciones generales que no están ligadas a un modelo específico
- Policies: clases organizadas por modelo, ideales para reglas de autorización relacionadas a un recurso específico (ej. "solo el dueño de un post puede editarlo")
- Bonus: menciona el método `authorize()` en controllers o el helper `@can` en Blade

---

## Pregunta 19: Eventos y Listeners
¿Qué son los eventos y los listeners en Laravel? Da un ejemplo de cuándo los usarías.

**Puntos clave a evaluar:**
- Explica que los eventos permiten desacoplar partes de la aplicación: algo "sucede" (evento) y una o varias clases "reaccionan" a eso (listeners), sin que estén directamente conectadas
- Da un ejemplo correcto (ej. evento `UsuarioRegistrado` que dispara un listener que envía un correo de bienvenida, sin que esa lógica esté metida en el controller)
- Menciona la ventaja: se pueden agregar varios listeners a un mismo evento sin tocar el código que lo dispara
- Bonus: menciona que los listeners se pueden poner en cola para procesarse en segundo plano

---

## Pregunta 20: Caché en Laravel
¿Para qué usarías el sistema de caché de Laravel? Da un ejemplo de qué guardarías en caché y por qué.

**Puntos clave a evaluar:**
- Explica que la caché permite guardar temporalmente resultados costosos de calcular u obtener, para no repetir ese trabajo en cada petición
- Da un ejemplo correcto (ej. resultados de una consulta pesada que no cambia seguido, configuración, resultados de una llamada a una API externa)
- Menciona algún driver de caché disponible (archivo, database, Redis, Memcached)
- Bonus: menciona la invalidación de caché como un reto importante (saber cuándo actualizar o borrar el dato guardado)

---

## Pregunta 21: Transacciones de base de datos
¿Qué es una transacción de base de datos y cómo la manejarías en Laravel? Da un ejemplo de cuándo sería necesaria.

**Puntos clave a evaluar:**
- Explica que una transacción agrupa varias operaciones de base de datos para que se ejecuten todas juntas o ninguna (atomicidad)
- Da un ejemplo correcto (ej. transferir dinero entre cuentas: restar de una y sumar a otra deben pasar juntas o revertirse ambas si algo falla)
- Menciona el uso de `DB::transaction()` o los métodos `beginTransaction`, `commit` y `rollback`
- Bonus: menciona qué pasa si ocurre una excepción dentro de la transacción (se revierte automáticamente con `DB::transaction()`)

---

## Pregunta 22: Patrón Repository
¿Qué es el patrón Repository y qué ventaja aportaría aplicarlo en un proyecto Laravel, en vez de usar Eloquent directo en los controllers?

**Puntos clave a evaluar:**
- Explica que el patrón Repository agrega una capa intermedia entre la lógica de negocio y el acceso a datos
- Menciona la ventaja principal: desacopla la aplicación de Eloquent específicamente, facilitando cambiar la fuente de datos o hacer pruebas con datos falsos (mocks)
- Puede mencionar que ayuda a mantener los controllers más delgados y organizados
- Bonus: menciona que no siempre es necesario - en proyectos pequeños puede ser una capa de complejidad innecesaria

---

## Pregunta 23: Facades
¿Qué son los Facades en Laravel? Da un ejemplo de uno que hayas usado y explica cómo funcionan por dentro, a grandes rasgos.

**Puntos clave a evaluar:**
- Explica que un Facade es una forma de acceder a servicios registrados en el Service Container usando una sintaxis estática, más simple de leer
- Da un ejemplo correcto (ej. `Cache`, `Route`, `DB`, `Auth`)
- Menciona a grandes rasgos que por dentro no son realmente estáticos, resuelven una instancia real del servicio detrás de escena
- Bonus: menciona alguna crítica común a los Facades (pueden dificultar el testing o esconder las dependencias reales de una clase)

---

## Pregunta 24: Colecciones de Laravel
¿Qué son las Collections en Laravel y en qué se diferencian de un array normal de PHP?

**Puntos clave a evaluar:**
- Explica que una Collection es un envoltorio orientado a objetos sobre arrays, con muchos métodos útiles para transformar y trabajar con datos
- Da un ejemplo de algún método útil (ej. filtrar, ordenar, agrupar, mapear datos)
- Menciona que Eloquent devuelve Collections por defecto al traer varios registros
- Bonus: menciona que permiten encadenar varias operaciones de forma legible, en vez de escribir varios bucles separados

---

## Pregunta 25: Comandos Artisan personalizados
¿Qué es Artisan en Laravel? Da un ejemplo de un caso donde crearías un comando Artisan personalizado.

**Puntos clave a evaluar:**
- Explica que Artisan es la herramienta de línea de comandos de Laravel, usada para tareas como migraciones, generar archivos, o correr el servidor
- Menciona que se pueden crear comandos propios para tareas repetitivas o de mantenimiento
- Da un ejemplo correcto (ej. un comando para limpiar registros viejos de la base de datos, generar reportes, o importar datos desde un archivo)
- Bonus: menciona que estos comandos se pueden programar para correr automáticamente con el Task Scheduling de Laravel

---

## Pregunta 26: Rate Limiting
¿Qué es el rate limiting y para qué lo usarías en una API construida con Laravel?

**Puntos clave a evaluar:**
- Explica que es limitar cuántas peticiones puede hacer un usuario o IP en un periodo de tiempo determinado
- Menciona el propósito: evitar abuso de la API, prevenir ataques de fuerza bruta, o proteger el servidor de sobrecarga
- Menciona que Laravel lo implementa como un middleware (throttle)
- Bonus: menciona que se puede configurar distinto por ruta o por tipo de usuario (ej. usuarios autenticados con límite más alto)

---

## Pregunta 27: Almacenamiento de archivos
¿Cómo maneja Laravel el almacenamiento de archivos subidos por el usuario? Menciona alguna consideración de seguridad al permitir subir archivos.

**Puntos clave a evaluar:**
- Menciona el Storage facade y el concepto de "discos" (local, público, o servicios en la nube como S3)
- Explica que los archivos subidos deben validarse (tipo de archivo, tamaño máximo) antes de guardarlos
- Menciona algún riesgo de seguridad (ej. permitir subir archivos ejecutables, o no validar el tipo real del archivo y no solo la extensión)
- Bonus: menciona que es buena práctica no exponer directamente la ruta real del archivo en el servidor

---

## Pregunta 28: Soft Deletes
¿Qué es un "soft delete" en Laravel y en qué se diferencia de borrar un registro normalmente?

**Puntos clave a evaluar:**
- Explica que un soft delete no borra el registro físicamente de la base de datos, sino que marca una columna (normalmente `deleted_at`) con la fecha de borrado
- Menciona la ventaja: se puede "recuperar" el registro después, y mantiene el historial de datos
- Menciona que se activa agregando un trait al modelo (SoftDeletes) y que Eloquent automáticamente excluye esos registros de las consultas normales
- Bonus: menciona el método para consultar incluyendo los borrados (`withTrashed`) o solo los borrados (`onlyTrashed`)

---

## Pregunta 29: Relaciones polimórficas
¿Qué es una relación polimórfica en Eloquent? Da un ejemplo de un caso donde la usarías.

**Puntos clave a evaluar:**
- Explica que permite que un modelo pertenezca a más de un tipo de modelo distinto usando una sola relación
- Da un ejemplo correcto (ej. un modelo Comentario que puede pertenecer tanto a un Post como a un Video, o un modelo Imagen que puede pertenecer a distintos tipos de contenido)
- Menciona que Laravel maneja esto guardando el tipo y el ID del modelo relacionado en la misma tabla
- Bonus: menciona la diferencia entre relación polimórfica uno a muchos y muchos a muchos

---

## Pregunta 30: Seguridad básica en Laravel
Menciona al menos dos riesgos de seguridad comunes en aplicaciones web (por ejemplo CSRF, XSS, o inyección SQL) y cómo Laravel ayuda a protegerte de ellos por defecto.

**Puntos clave a evaluar:**
- CSRF: explica que es cuando un atacante hace que el navegador de un usuario autenticado envíe una petición sin que el usuario lo sepa; menciona que Laravel protege esto con un token CSRF automático en los formularios
- XSS: explica que es cuando se inyecta código malicioso (normalmente JavaScript) que se ejecuta en el navegador de otro usuario; menciona que Blade escapa el contenido por defecto al mostrar variables
- Inyección SQL: explica que ocurre cuando se concatenan datos del usuario directo en una consulta SQL sin sanitizar; menciona que Eloquent y el Query Builder usan consultas preparadas (parametrizadas) por defecto, lo que previene esto
- Bonus: menciona que aun así, hay que tener cuidado al usar consultas raw sin parametrizar