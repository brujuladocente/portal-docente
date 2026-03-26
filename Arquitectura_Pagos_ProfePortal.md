# Arquitectura de Pagos - ProfePortal

Este documento describe la arquitectura definitiva del sistema de cobros automatizados de **Brújula Docente / ProfePortal**, implementada mediante integraciones nativas con la API de Mercado Pago y Google Apps Script.

---

## 1. El Flujo Frontend (El Inicio del Viaje)
Todo comienza en el archivo `index.html`. Cuando un docente decide suscribirse o abonar el mes manual:
1. El usuario ingresa su correo electrónico en el modal interactivo de la página web.
2. Al hacer clic en "Continuar", el sistema bloquea los botones y extrae el email ingresado.
3. El frontend **jamás redirecciona directamente a Mercado Pago**. En su lugar, hace una petición silenciosa en segundo plano (vía HTTP `fetch`) hacia el **Servidor Puente** (Google Apps Script).

---

## 2. El Servidor Puente (Generación Dinámica)
El archivo `webhook_mercado_pago.gs` tiene una función llamada `doGet`. Su trabajo es interactuar directamente de servidor a servidor con Mercado Pago antes de que el usuario vea la pantalla de cobro.
* **Si es Pago Único:** 
  LLama a la API `POST /checkout/preferences`. Construye un "carrito virtual" de $2500 e incrusta el correo del docente en el campo secreto `external_reference`. La API devuelve una URL única (`init_point`).
* **Si es Suscripción:**
  Devuelve la URL oficial de la pasarela de suscripciones concatenando el email por la URL, ya que esta pasarela nativa respeta los atributos (a diferencia de los links cortos `mpago.la`).

El frontend recibe esta URL y redirige instantáneamente al usuario. En este punto, **el correo del usuario quedó blindado e inyectado** en las entrañas de la factura virtual en Mercado Pago. Aunque el usuario inicie sesión con la billetera de su abuela, Mercado Pago mantendrá el registro de que el pago es para *ese* email.

---

## 3. El Pago y la Notificación IPN / Webhook
El usuario consolida su pago con éxito en la plataforma de MercadoPago.
Inmediatamente, Mercado Pago lanza un aviso en tiempo real (HTTP POST) apuntando de vuelta a nuestro Google Apps Script.

La función `doPost` entra en acción:
1. Intercepta la petición e identifica el número único de la transacción (`paymentId`).
2. Se conecta otra vez con Mercado Pago (API `GET /v1/payments/{paymentId}`) usando el Token de Producción para verificar matemáticamente que el pago sea real, aprobado y lícito (evita hacking y fraudes).
3. **Extracción:** Cosecha el `external_reference` (el correo bloqueado) y, por las dudas, resguarda el `payer.email` (el de la cuenta real de Mercado Pago).

---

## 4. Inyección en Base de Datos (Database Manager)
Con los datos confirmados, el motor de Apps Script (`actualizarGoogleSheet`) explora los registros de tu Google Sheet:
* **Si el usuario no existe:** Le crea una fila de bienvenida rotulada como "Por Completar", coloca el email en la columna de destino (Col C), y marca las columnas transaccionales: estado "Alta", pago "PAGADO", plan "Premium" y calcula el Vencimiento exacto a 30 días vista.
*  Le dispara inmediatamente un correo electrónico oficial dándole la bienvenida e invitándolo a hacer clic en tu enlace de **Google Forms** para seleccionar las materias de interés.
* **Si el usuario ya existe:** Actualiza su fila preexistente re-activándole el estado PAGADO y extendiendo su vencimiento.

---

## 5. Cierre: El Formulario de Recolección (El Merge)
Dado que el Webhook ya se encargó de capturar el dinero, el correo y marcar al usuario como Premium, el Formulario de Google asume un rol puramente **demográfico**.

1. El usuario, desde el correo de bienvenida, abre tu Google Form y solamente completa su Nombre, el mismo Email y los Distritos/Cargos de interés.
2. Al enviarlo, Google Forms inserta una nueva fila al final del documento.
3. El script incrustado en dicho Formulario (`Código.gs` interno del Form) detectará esto e iniciará la operación **Merge** (Fusión): cruzará la tabla buscando la fila "Por Completar / PAGADO" que creó el webhook original, copiará sus atributos financieros a esta nueva fila rica en datos, y destruirá la fila temporaria anterior, dejando un solo perfil maestro inmaculado.

---

## 6. Guía de Resolución de Problemas Comunes (Troubleshooting)

### Caso 1: El usuario pagó pero el Formulario lo detecta como GRATIS (Desajuste de Correos)
* **El Problema:** El usuario ingresó `profe_trabajo@gmail.com` en nuestra página web al momento de pagar. El Webhook registró el pago exitosamente bajo ese correo. Sin embargo, cuando el usuario abrió el Formulario de Google, ingresó `profe_personal@gmail.com`. Al no ser exactos, el script "Merge" del formulario no encontró ninguna fila huérfana de pago asociada a `profe_personal@gmail.com` y lo catalogó automáticamente como plan PENDIENTE/Gratis, enviándole por ende el "Mail Automático de Advertencia".
* **La Solución (Manual):**
  1. El docente, al recibir la advertencia, te responderá al correo de soporte con su comprobante de pago.
  2. Vas a tu Google Sheet y filtrás la Columna J (Email de Cuenta MP) o la Columna C buscando el correo que te menciona o el de su comprobante.
  3. Vas a encontrar una fila que dirá `Por Completar | PAGADO | Premium` (la que generó el webhook original pero jamás hizo Merge) y otra fila completa con `Su Nombre | PENDIENTE | Gratis | Distritos completados` (la del formulario desajustado).
  4. Manualmente, copiás el estado `PAGADO`, `Premium` y la `Fecha de Vencimiento` de la fila huérfana, y los pegás en la fila de su perfil real para habilitarle el servicio.
  5. Borrás la fila huérfana. ¡Listo, problema resuelto administrativamente!

### Caso 2: El Excel muestra '#REF!' en columnas K o L
* **El Problema:** Borraste alguna pestaña vieja o sobreescribiste por error las celdas de la primera fila.
* **La Solución:** Este es un error humano de fórmula en el Sheet. Recordá que la Columna K (Estado) usa una fórmula `=ARRAYFORMULA(...)` que lee desde el Formulario 2 (Bajas). Simplemente restaurá la fórmula en la fila 1 de dicha columna. La Columna L ya NO usa ArrayFormula en la nueva arquitectura.

### Caso 3: Dos docentes diferentes pagan con la misma cuenta de Mercado Pago
* **La Ventaja:** No hay conflicto absoluto. El Webhook está diseñado para basarse estrictamente en el parámetro `external_reference` (el ADN insertado en el `index.html`).
* **Operación:** Si `profe1` paga con la billetera de María y luego `profe2` paga también con la billetera de María, el Webhook creará (o ubicará) dos filas distintas en el Excel (una para cada profe) y les asignará el pago individual a cada uno. El Excel tendrá en ambas filas el mismo `Email MP` (María) pero los servicios Premium estarán asignados a cada profe correctamente.
