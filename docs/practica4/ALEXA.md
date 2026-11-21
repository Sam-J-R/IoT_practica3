# Skill de Alexa — práctica 4

Pasos para actualizar la Skill que ya funciona con la práctica 3, y la lista de frases para probarla. La [documentación de Alexa de la práctica 3](../ALEXA.md) se conserva sin cambios, con sus capturas y resultados.

No cambian el nombre de invocación (`tendedero inteligente`), el idioma (`es-MX`), el endpoint ni el Skill ID.

## 1. Actualizar el modelo de interacción

1. Abrir la Skill en la **Alexa Developer Console → Build**.
2. En el menú izquierdo, abrir **Interaction Model → JSON Editor**.
3. Reemplazar todo el contenido por [interaction-model-es-MX.json](../../alexa/interaction-model-es-MX.json).
4. Elegir **Save** y después **Build skill**. Esperar a que la compilación termine sin errores.

Hacerlo **después** de que la Lambda nueva esté desplegada ([GUIA_AWS.md](GUIA_AWS.md), paso 5). Con el modelo nuevo y la Lambda antigua, los intents nuevos no tendrían quién los atienda.

## 2. Qué cambió en el modelo

| Intent | Cambio |
|---|---|
| `VincularThingIntent`, `CambiarThingIntent` | El slot `thing_name` (`AMAZON.SearchQuery`) pasa a ser `codigo` (`AMAZON.NUMBER`). Alexa pide el código si falta y lo confirma antes de enviarlo. |
| `AbrirCubiertaIntent` | Se reemplaza por `ExponerTendederoIntent`. |
| `CerrarCubiertaIntent` | Se reemplaza por `ResguardarTendederoIntent`. |
| `ConsultarCubiertaIntent` | Se reemplaza por `ConsultarPosicionIntent`. |
| `CalibrarSensorIntent` | **Nuevo.** Slot `condicion` del tipo propio `CondicionSensor` (`seco` / `mojado`, con sinónimos). |
| `ConsultarCalibracionIntent` | **Nuevo.** |
| `DesvincularThingIntent`, `ConsultarAguaIntent` | Solo cambian algunas frases ("objeto" pasa a "tendedero"). |

### Confirmación del código

El modelo incluye una sección `dialog` con delegación automática. Para vincular y cambiar, Alexa se encarga de dos cosas antes de llamar a la Lambda:

- Si el usuario no dice el código, lo pide: «Dime el código de seis dígitos que está en la etiqueta de tu tendedero».
- Cuando lo tiene, lo repite dígito por dígito y pregunta si es correcto. Si el usuario dice que no, lo vuelve a pedir.

Así se evita vincular un tendedero equivocado por un error de reconocimiento. La Lambda valida igualmente el formato y la existencia del código.

## 3. Frases para probar

Usar **Test → Development**, en español (MX). Los códigos son los de ejemplo de la [guía de AWS](GUIA_AWS.md): `483920` para el tendedero físico y `715204` para el de prueba.

| # | Frase | Respuesta esperada |
|---|---|---|
| 1 | abre tendedero inteligente | Bienvenida con las operaciones disponibles. |
| 2 | hay agua en el sensor *(sin vínculo)* | «No tienes un tendedero vinculado…» |
| 3 | vincula mi tendedero con el código 715204 | Alexa confirma el código; al responder «sí»: «He vinculado tu tendedero…» |
| 4 | vincula mi tendedero | Alexa pide el código. |
| 5 | vincula mi tendedero con el código 999999 | «No encontré un tendedero con ese código…» |
| 6 | hay agua en el sensor | «El sensor detecta agua» o «El sensor no detecta agua». |
| 7 | dónde está el tendedero | «Según el último reporte, el tendedero está…» |
| 8 | resguarda la ropa | «He solicitado que el tendedero quede resguardado…» |
| 9 | expón el tendedero | «He solicitado que el tendedero quede expuesto…» |
| 10 | cambia mi tendedero al código 483920 | Confirma el código y vincula el tendedero físico. |
| 11 | calibra el sensor seco | «He solicitado la calibración en seco… di: calibra el sensor mojado». |
| 12 | calibra el sensor mojado | «He solicitado la calibración con agua…» |
| 13 | calibra el sensor | Alexa pregunta en qué condición está el sensor. |
| 14 | cómo está la calibración | Aplicada, rechazada, caducada, pendiente o de fábrica. |
| 15 | desvincula mi tendedero | «He eliminado la vinculación de tu tendedero». |
| 16 | ayuda | Lista de operaciones. |

Notas para la prueba:

- Las frases 11 a 14 necesitan el tendedero físico vinculado (frase 10), encendido y conectado. Con el Thing de prueba, la calibración queda siempre «pendiente», porque no hay un ESP32 que la atienda.
- Para la frase 11 el sensor debe estar seco; para la 12, mojado. Si se pide «seco» con el sensor mojado, la calibración se rechaza y se conservan los valores anteriores.
- Cerrar la conversación no elimina el vínculo.

## 4. Límites conocidos

- El modelo no se pudo compilar ni probar en la consola de Alexa desde el repositorio. La primera compilación es la verificación real del JSON, en particular de la sección `dialog` y de la confirmación del código con SSML.
- Si la confirmación del código diera problemas en la consola, se puede poner `"confirmationRequired": false` en el slot `codigo` de los dos intents y quitar el *prompt* `Confirm.Slot…`. La Lambda funciona igual con o sin confirmación.
- La Lambda responde a la calibración sin esperar al dispositivo. El resultado se consulta después con «cómo está la calibración».
