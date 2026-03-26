// ==========================================
// SCRIPT PARA GOOGLE FORMS (Código.gs)
// TRABAJA EN CONJUNTO CON EL WEBHOOK DE MERCADO PAGO
// ==========================================

// INSTRUCCIONES DE USO:
// 1. En tu Google Form (el de Altas), andá a los 3 puntitos > Editor de Secuencias de Comandos.
// 2. Borrá todo lo que haya y pegá esto.
// 3. Andá al menú de la izquierda al relojito (Disparadores/Triggers).
// 4. Creá un disparador nuevo: Ejecutar 'onFormSubmit' -> Desde el formulario -> Al enviar el formulario.

function onFormSubmit(e) {
  // Entorno de la hoja de cálculo ligada al formulario
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Respuestas de formulario 1');
  if (!sheet) return;
  
  const rowIndex = e.range.getRow(); // La fila nueva que acaba de insertar Forms
  const rowData = sheet.getRange(rowIndex, 1, 1, sheet.getLastColumn()).getValues()[0];
  
  // El correo con el que quieren las alertas (Columna C es el índice 2)
  const nuevoEmail = String(rowData[2]).trim().toLowerCase(); 
  if (!nuevoEmail) return;

  // Traer toda la columna C para buscar a su gemelo "huérfano" (creado por el Webhook de Mercado Pago antes)
  const MAX_ROWS = sheet.getLastRow();
  const emailsData = sheet.getRange(1, 3, MAX_ROWS, 1).getValues();

  let filaHuerfana = -1;

  // Buscamos la fila del Webhook
  for (let i = 0; i < emailsData.length; i++) {
    // Filtramos la fila del form recién inyectada
    if (i === (rowIndex - 1)) continue; 
    
    let cellEmail = String(emailsData[i][0]).trim().toLowerCase();
    if (cellEmail === nuevoEmail) {
      // Chequear que realmente sea la fila insertada por el webhook
      let pago = sheet.getRange(i + 1, 12).getValue(); // Col L
      let nombre = sheet.getRange(i + 1, 2).getValue(); // Col B
      
      if (pago === "PAGADO" || nombre === "Por Completar") {
         filaHuerfana = i + 1;
         break;
      }
    }
  }

  if (filaHuerfana > -1) {
    // ¡MATCH! El usuario pagó primero y llenó el form después.
    // Extraemos su estatus financiero de oro
    const oroEmailMP = sheet.getRange(filaHuerfana, 10).getValue(); // Col J
    const oroEstadoPago = sheet.getRange(filaHuerfana, 12).getValue(); // Col L
    const oroPlan = sheet.getRange(filaHuerfana, 13).getValue(); // Col M
    const oroVencimiento = sheet.getRange(filaHuerfana, 14).getValue(); // Col N

    // Traspasamos el estatus a su nueva fila de perfil
    sheet.getRange(rowIndex, 10).setValue(oroEmailMP);
    sheet.getRange(rowIndex, 12).setValue(oroEstadoPago);
    sheet.getRange(rowIndex, 13).setValue(oroPlan);
    sheet.getRange(rowIndex, 14).setValue(oroVencimiento);

    // MERGE COMPLETADO: Decapitamos la fila huérfana de Mercado Pago para no duplicar datos
    sheet.deleteRow(filaHuerfana);
    
  } else {
    // Es un usuario que NO pagó por la web, se equivocó de mail, o le pasaron el link filtrado
    // Inicializamos su fila como Gratis
    sheet.getRange(rowIndex, 12).setValue("PENDIENTE");
    sheet.getRange(rowIndex, 13).setValue("Gratis");
    
    // DISPARAMOS EL CORREO AUTOMÁTICO DE ADVERTENCIA
    const asunto = "Sobre tus Alertas en ProfePortal - Información importante";
    const cuerpo = "¡Hola, colega!\n\n" +
                   "Acabamos de recibir tu formulario de preferencias. Vemos que aún no se registra ningún pago asociado a este correo en particular, por lo que tus alertas comenzarán a funcionar bajo el Plan Gratuito (limitado a 1 materia y 1 distrito).\n\n" +
                   "💡 Si ya realizaste el pago para el Plan Premium, ¡no te preocupes! Es muy probable que hayas ingresado en la página web un correo distinto al que pusiste en el formulario.\n\n" +
                   "Envianos un mensajito respondiendo a este correo (o a brujuladocentesur@gmail.com) con tu comprobante de Mercado Pago y te lo solucionamos manualmente en el acto.\n\n" +
                   "Si todavía no te pasaste a Premium y querés recibir alertas ilimitadas para no perderte ningún cargo, podés hacerlo desde nuestra web: https://facudpascielli.github.io/apd-omni/\n\n" +
                   "¡Gracias por ser parte de la comunidad de Brújula Docente! 🧭";
                   
    try {
      MailApp.sendEmail({
        to: nuevoEmail,
        subject: asunto,
        body: cuerpo,
        name: "ProfePortal Web"
      });
    } catch (err) {
      console.error("No se pudo enviar correo de advertencia a: " + nuevoEmail);
    }
  }
}
