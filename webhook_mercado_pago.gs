// webhook_mercado_pago.gs
// ==========================================
// CONFIGURACIÓN INICIAL (DEBES RELLENAR ESTO)
// ==========================================
const SHEET_ID = '14UNkDXKDw3pWLeVBnElcU4GvEznO9g5G6qhkzwU78sI'; // ID del Google Sheet
const SHEET_NAME = 'Respuestas de formulario 1'; 
const MP_ACCESS_TOKEN = 'APP_USR-ACA_VA_TU_ACCESS_TOKEN_REAL_DE_PRODUCCION'; // Token de MP
const URL_FORMULARIO_INGRESO = 'https://tuweb.com/index.html#modalFree'; // URL de tu formulario/modal

// ==========================================
// FUNCIÓN PARA LOGUEAR EN LA PLANILLA
// ==========================================
function logToSheet(mensaje) {
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) return;
    const row = [new Date(), "[LOG_WEBHOOK]", mensaje, "", "", "", "", "", "", "", "", "", ""];
    const primeraVacia = findFirstEmptyRow(sheet);
    sheet.getRange(primeraVacia, 1, 1, row.length).setValues([row]);
  } catch(e) {
    console.error("Error guardando log: " + e);
  }
}

// ==========================================
// FUNCIÓN PRINCIPAL PARA EL WEBHOOK
// ==========================================
function doPost(e) {
  try {
    if (typeof e !== 'undefined' && e.postData && e.postData.contents) {
      const payload = JSON.parse(e.postData.contents);
      const action = payload.action || payload.topic || payload.type;
      
      logToSheet("Recibido POST de MP. Action/Topic: " + action);
      
      // Manejar notificaciones de pagos individuales o cobros de suscripción
      if (action === 'payment' || action === 'payment.created' || action === 'payment.updated') {
        const paymentId = (payload.data && payload.data.id) ? payload.data.id : null;
        
        let finalId = paymentId;
        if (!finalId && payload.resource) {
          const parts = payload.resource.split('/');
          finalId = parts[parts.length - 1];
        }
        
        if (finalId) {
          logToSheet("ID de pago detectado: " + finalId + ". Verificando en API...");
          procesarNotificacionDePago(finalId);
        } else {
          logToSheet("Advertencia: Se recibió un action payment pero no se encontró el ID.");
        }
      }
      
      return ContentService.createTextOutput("OK").setMimeType(ContentService.MimeType.TEXT);
    }
    
    logToSheet("Error: Datos recibidos vacíos o no reconocidos.");
    return ContentService.createTextOutput("Datos no reconocidos.").setMimeType(ContentService.MimeType.TEXT);

  } catch (error) {
    logToSheet("Error fatal en doPost: " + error.toString());
    return ContentService.createTextOutput("Error").setMimeType(ContentService.MimeType.TEXT);
  }
}

// ==========================================
// CONSULTA A MERCADO PAGO Y ACTUALIZACIÓN BD
// ==========================================
function procesarNotificacionDePago(paymentId) {
  const url = 'https://api.mercadopago.com/v1/payments/' + paymentId;
  const options = {
    'method': 'get',
    'headers': {
      'Authorization': 'Bearer ' + MP_ACCESS_TOKEN
    },
    'muteHttpExceptions': true
  };
  
  const response = UrlFetchApp.fetch(url, options);
  if (response.getResponseCode() === 200) {
    const paymentInfo = JSON.parse(response.getContentText());
    
    // Solo actuamos si el pago está aprobado
    if (paymentInfo.status === 'approved') {
      logToSheet("Pago " + paymentId + " APROBADO. Buscando email identificativo...");
      
      let userEmail = paymentInfo.external_reference;
      if (!userEmail || userEmail === 'null' || userEmail === '') {
        if (paymentInfo.payer && paymentInfo.payer.email) {
          userEmail = paymentInfo.payer.email;
        }
      }
      
      if (userEmail) {
        userEmail = String(userEmail).trim().toLowerCase();
        logToSheet("Email encontrado: " + userEmail + ". Actualizando planilla...");
        actualizarGoogleSheet(userEmail, paymentInfo);
      } else {
        logToSheet("Fallo: Pago aprobado " + paymentId + " PERO NO TIENE EMAIL EN external_reference ni en payer.email.");
      }
    } else {
      logToSheet("Se ignoró el pago " + paymentId + " porque su estado es: " + paymentInfo.status);
    }
  } else {
    // Aquí es donde caería el 1234567890 falso porque devuelve 404
    logToSheet("Atención: Falló la validación del ID " + paymentId + ". MP devolvió código " + response.getResponseCode() + ". Detalles: " + response.getContentText());
  }
}

function actualizarGoogleSheet(email, paymentInfo) {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);
  
  if (!sheet) {
    console.error("Hoja no encontrada.");
    return;
  }
  
  const MAX_ROWS = sheet.getLastRow();
  // Traer toda la columna C (Email) empezando desde la fila 1 hasta la última con datos
  const emailsData = sheet.getRange(1, 3, MAX_ROWS || 1, 1).getValues(); 
  
  let filaEncontrada = -1;
  
  // Buscar de abajo hacia arriba para agarrar su último registro si tiene varios
  for (let i = emailsData.length - 1; i >= 0; i--) {
    let cellEmail = String(emailsData[i][0]).trim().toLowerCase();
    if (cellEmail === email) {
      filaEncontrada = i + 1; // 1-indexed
      break;
    }
  }
  
  // Calcular Vencimiento = hoy + 30 días
  const hoy = new Date();
  const vencimiento = new Date();
  vencimiento.setDate(hoy.getDate() + 30);
  const fechaVencString = vencimiento.toLocaleDateString('es-AR');

  if (filaEncontrada > -1) {
    // ---- EL USUARIO YA EXISTE EN LA PLANILLA ----
    // Columna L (12): Estado de pago -> PAGADO
    // Columna M (13): Plan -> Premium
    // Columna N (14): Vencimiento Premium (Opcional, agregarla a tu sheet)
    sheet.getRange(filaEncontrada, 12).setValue("PAGADO");
    sheet.getRange(filaEncontrada, 13).setValue("Premium");
    sheet.getRange(filaEncontrada, 14).setValue(fechaVencString);
    
  } else {
    // ---- EL USUARIO NO EXISTE TODAVÍA ----
    // Crearle una fila 'placeholder' con saldo a favor
    // [A:Fecha, B:Nombre, C:Email, D:Dist1, E:Dist2, F:Dist3, G:Nivel, H:Materia, I:Duda, J:EmailMP, K:Estado, L:Pago, M:Plan, N:Vencimiento]
    const nuevaFila = [
      new Date(),       // A
      "Por Completar",  // B (Nombre)
      email,            // C (Email)
      "", "", "", "", "", "", // D - I
      email,            // J (EmailMP)
      "Alta",           // K (Estado Activo)
      "PAGADO",         // L
      "Premium",        // M
      fechaVencString   // N
    ];
    
    // findFirstEmptyRow local para no meterla en la fila 1000 de form de google
    const primeraVacia = findFirstEmptyRow(sheet);
    sheet.getRange(primeraVacia, 1, 1, nuevaFila.length).setValues([nuevaFila]);
    
    // MANDARLE EL MAIL PARA QUE COMPLETE SUS DISTRITOS
    enviarEmailCompletarDatos(email);
  }
}

function findFirstEmptyRow(sheet) {
  const columnAData = sheet.getRange(1, 1, sheet.getMaxRows(), 1).getValues();
  for (let i = 0; i < columnAData.length; i++) {
    if (!columnAData[i][0] || String(columnAData[i][0]).trim() === "") {
       return i + 1;
    }
  }
  return sheet.getMaxRows() + 1;
}

// ==========================================
// ENVÍO DE EMAIL AUTOMÁTICO VÍA GMAIL
// ==========================================
function enviarEmailCompletarDatos(destinatario) {
  const asunto = "¡Pago exitoso! Activá tus Alertas Premium de ProfePortal 🚀";
  
  const cuerpo = "¡Hola!\n\n" +
               "Hemos procesado tu pago correctamente y tu cuenta ya es Premium por 30 días. 🎉\n\n" +
               "Sin embargo, notamos que nos faltan tus datos de búsqueda (las materias y distritos que te interesan).\n\n" +
               "Para configurar tus alertas, por favor ingresá al siguiente enlace y completá el Formulario Gratis usando ESTE MISMO CORREO (" + destinatario + "). Nuestro sistema reconocerá automáticamente que sos usuario Premium en cuanto presiones 'Enviar'.\n\n" +
               "👉 Enlace: " + URL_FORMULARIO_INGRESO + "\n\n" +
               "¡Gracias por confiar en Brújula Docente / ProfePortal!\n" +
               "Cualquier duda, podés responder a este correo.";
               
  try {
    MailApp.sendEmail({
      to: destinatario,
      subject: asunto,
      body: cuerpo,
      name: "ProfePortal Web"
    });
    console.log("Email enviado a " + destinatario);
  } catch (error) {
    console.error("Error enviando email a " + destinatario + ": " + error);
  }
}
