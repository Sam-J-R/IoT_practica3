# Evidencias de la Skill de Alexa (práctica 4)

- **Fecha:** 24 de noviembre de 2026, entre las 11:39 y las 12:40 (hora de Bolivia, UTC−4).
- **Responsable:** Katherine Montaño (encargada de Alexa).
- **Interfaz:** Alexa Developer Console, simulador en **Development**, idioma **Spanish (MX)**. Entrada por texto.
- **Modelo:** [interaction-model-es-MX.json](../../../../alexa/interaction-model-es-MX.json), construido sin errores el 24/11/2026 a las 11:50 (captura 07).
- **Procedimiento y frases:** [docs/practica4/ALEXA.md](../../../practica4/ALEXA.md) §3.

Estas son las primeras pruebas de la Skill de la P4 en el simulador real. Las pruebas de [resultados_p4/pruebas-aws-consola.md](../../../../resultados_p4/pruebas-aws-consola.md) inyectaban eventos JSON en la Lambda y no pasaban por el modelo de interacción. Estas pruebas sí: verifican el reconocimiento de las frases, los slots, la confirmación del código y la delegación del diálogo.

**Tendederos usados.** Un mismo usuario de Alexa vinculó dos tendederos:

| Nombre dado por voz | Código | Thing | ESP32 |
|---|---|---|---|
| `terraza` | `483920` | `tendedero-inteligente` | Sí (físico) |
| `patio` | `715204` | `tendedero-prueba2` | No (Thing de prueba) |

Las pruebas 16 a 32 se hicieron con un solo tendedero vinculado, el físico (`terraza`). Las órdenes y las calibraciones de esas pruebas llegaron al ESP32 real.

## Configuración del modelo

| Archivo | Qué muestra |
|---|---|
| [01-invocacion.png](01-invocacion.png) | Nombre de invocación `tendedero inteligente`, idioma Spanish (MX) |
| [02a-intents-lista.png](02a-intents-lista.png) | Intents personalizados (primera parte): Vincular, Desvincular, Listar, ConsultarAgua, Exponer, Resguardar y ConsultarPosicion, con el número de frases y slots |
| [02b-intents-lista.png](02b-intents-lista.png) | Segunda parte: CalibrarSensor, ConsultarCalibracion, CambiarModo, ConsultarModo, ConfigurarEspera, EncenderLuz, ApagarLuz y ConsultarLuz |
| [02c-intents-lista.png](02c-intents-lista.png) | Intents integrados (Cancel, Stop, Help, Fallback y NavigateHome): 20 intents en total |
| [03-slot-codigo-confirmacion.png](03-slot-codigo-confirmacion.png) | `VincularThingIntent`: slot `codigo` (`AMAZON.NUMBER`) y slot `nombre` (`NombreTendedero`) |
| [04-frases-vincular.png](04-frases-vincular.png) | Frases de ejemplo de `VincularThingIntent` (14), con el slot `{codigo}` y la frase sin código |
| [05-tipo-condicion-sensor.png](05-tipo-condicion-sensor.png) | `CalibrarSensorIntent`: slot `condicion` del tipo propio `CondicionSensor` y slot `nombre` |
| [06-json-editor.png](06-json-editor.png) | Modelo pegado en el JSON Editor |
| [07-modelo-construido.png](07-modelo-construido.png) | Notificación **Build Completed**: el modelo compila, incluida la sección `dialog` |
| [08-endpoint.png](08-endpoint.png) | Endpoint de tipo AWS Lambda ARN hacia `tendedero-inteligente-alexa` en `us-east-2`, con el Skill ID y la cuenta tapados |

## Pruebas en el simulador

| # | Archivo | Frases | Respuesta obtenida | Requisito | Resultado |
|---|---|---|---|---|---|
| 10 | [10-inicio.png](10-inicio.png) | «abre tendedero inteligente» | «Bienvenido al tendedero inteligente. Puedes preguntar cómo está el tendedero, exponer o resguardar la ropa, cambiar el modo o encender la luz…» | Entrada a la Skill | PASA |
| 11 | [11-sin-vinculo.png](11-sin-vinculo.png) | «desvincula mi tendedero» → «hay agua en el sensor» | «No tienes un tendedero vinculado. Di: vincula mi tendedero con el código, seguido de los seis dígitos de la etiqueta.» | RF8 | PASA |
| 12 | [12-vincular-codigo-pide.png](12-vincular-codigo-pide.png) | «vincula mi tendedero» | «Dime el código de seis dígitos que está en la etiqueta de tu tendedero.» Alexa pide el slot que falta | RF7, diálogo | PASA |
| 13 | [13-vincular-confirmacion-nombre.png](13-vincular-confirmacion-nombre.png) | «vincula mi tendedero con el código cuatrocientos ochenta y tres mil novecientos veinte» → «sí» → «terraza» | «Entendí el código 483920. ¿Es correcto?» → «¿Qué nombre le pones a este tendedero?» → «He vinculado tu tendedero terraza…». El JSON muestra `Dialog.Delegate` | RF7, RF9 | PASA |
| 14 | [14-codigo-inexistente.png](14-codigo-inexistente.png) | «vincula mi tendedero» → «séxtuple nueve» | «Dime el código de seis dígitos que está en la etiqueta de tu tendedero.» Alexa no acepta un código que no reconoce como número de seis dígitos: no vincula ningún tendedero y vuelve a pedir el código | RF9 (entrada no válida) | PASA |
| 15 | [15-persistencia.png](15-persistencia.png) | «para» → «hay agua en el sensor» | «Hasta luego.» y después «El sensor no detecta agua.», sin volver a vincular | RF7 (persistencia) | PASA |
| 16 | [16-consulta-agua.png](16-consulta-agua.png) | «hay agua en el sensor» | «El sensor no detecta agua.» | RF4 | PASA |
| 17 | [17-consulta-posicion.png](17-consulta-posicion.png) | «cómo está el tendedero» | «Según el último reporte, el tendedero está resguardado porque ya oscureció. Volverá a salir cuando pasen 15 minutos sin agua y haya luz.» | RF6, motivo (R5) | PASA |
| 18 | [18-resguardar.png](18-resguardar.png) | «resguarda la ropa» | «El tendedero ya está resguardado.» La Lambda no repite una orden ya cumplida | RF5 | PASA |
| 19 | [19-exponer.png](19-exponer.png) | «expón el tendedero» (modo automático, de noche) | «Ya es de noche y el tendedero está en modo automático, así que la ropa se queda resguardada hasta que vuelva la luz. Si quieres exponerla igual, primero di: cambia a modo manual.» | §3.1, conflicto voz / R5 | PASA |
| 20 | [20-modo-manual.png](20-modo-manual.png) | «activa el modo manual» | «He activado el modo manual. El tendedero solo se moverá con tus órdenes, aunque llueva o anochezca.» | RF14 | PASA |
| 21 | [21-modo-automatico.png](21-modo-automatico.png) | «activa el modo automático» | «He activado el modo automático. El tendedero resguardará la ropa si llueve o anochece, y la volverá a exponer cuando haya luz y no llueva.» | RF14 | PASA |
| 22 | [22-consultar-modo.png](22-consultar-modo.png) | «en qué modo está» | «El tendedero está en modo automático… la vuelve a exponer después de 15 minutos sin agua, cuando hay luz.» Informa el modo y el parámetro `minutos_reexponer` | RF14 (consulta) | PASA |
| 23 | [23-configurar-espera.png](23-configurar-espera.png) | «espera cuarenta y cinco minutos para volver a exponer» | «Listo. En modo automático, la ropa volverá a exponerse después de 45 minutos sin agua, cuando haya luz.» | RF14 (modificación) | PASA |
| 24 | [24-conflicto-automatico.png](24-conflicto-automatico.png) | «hay agua en el sensor» → «expón el tendedero» (modo automático, con agua) | «El sensor detecta agua.» → «El sensor detecta agua y el tendedero está en modo automático, así que la ropa se queda resguardada. Si quieres exponerla igual, primero di: cambia a modo manual.» | §3.1, conflicto voz / R1 | PASA |
| 25 | [25-en-manual.png](25-en-manual.png) | «activa el modo manual» → «expón el tendedero» | «He solicitado que el tendedero quede expuesto. Espera la confirmación del dispositivo.» En modo manual, la voz tiene prioridad | RF5, §3.1 | PASA |
| 26 | [26-calibrar-seco.png](26-calibrar-seco.png) | «calibra el sensor seco» | «He solicitado la calibración en seco. Mantén el sensor seco unos segundos. Después moja la superficie del sensor y di: calibra el sensor mojado.» | Calibración | PASA (solicitud) |
| 27 | [27-calibrar-mojado.png](27-calibrar-mojado.png) | «calibra el sensor mojado» | «He solicitado la calibración con agua… Para saber el resultado, pregunta: cómo está la calibración.» | Calibración | PASA |
| 28 | [28-calibrar-sin-condicion.png](28-calibrar-sin-condicion.png) | «calibra el sensor» | «Dime en qué condición está el sensor. Puedes decir: calibra el sensor seco, o calibra el sensor mojado.» | Calibración, slot faltante | PASA |
| 29 | [29-consultar-calibracion.png](29-consultar-calibracion.png) | «cómo está la calibración» | «La última calibración, con el sensor mojado, se aplicó correctamente.» Resultado reportado por el ESP32 físico | Calibración | PASA |
| 30 | [30-luz-encender.png](30-luz-encender.png) | «enciende la luz» | «He pedido encender la luz del tendedero. Se apagará sola en 10 minutos.» | RF5 (LED) | PASA |
| 31 | [31-luz-apagar.png](31-luz-apagar.png) | «apaga la luz» | «He pedido apagar la luz del tendedero.» | RF5 (LED) | PASA |
| 32 | [32-luz-consultar.png](32-luz-consultar.png) | «cómo está la luz» | «La luz del tendedero está apagada.» | RF6 (LED) | PASA |
| 33 | [33-vincular-segundo.png](33-vincular-segundo.png) | «vincula mi tendedero con el código setecientos quince mil doscientos cuatro» → «sí» → «patio» | «Entendí el código 715204. ¿Es correcto?» → «He vinculado tu tendedero patio. Ahora tienes 2 tendederos: patio y terraza…» | Varios Things por usuario | PASA |
| 34 | [34-listar.png](34-listar.png) | «qué tendederos tengo» | «Tienes 2 tendederos: patio y terraza. En cada orden di en cuál…» | Varios Things | PASA |
| 35 | [35-pregunta-cual.png](35-pregunta-cual.png) | «resguarda la ropa» → «patio» | «¿En cuál tendedero? Tienes patio o terraza.» → «Tendedero patio: He solicitado que el tendedero quede resguardado…» La orden se conserva tras la pregunta (`Dialog.ElicitSlot`) | Varios Things | PASA |
| 36 | [36-nombre-en-frase.png](36-nombre-en-frase.png) | «hay agua en el tendedero de la terraza» | «Tendedero terraza: El sensor detecta agua.» | Varios Things | PASA |
| 37 | [37-nombre-inexistente.png](37-nombre-inexistente.png) | «resguarda el tendedero de la azotea» | «No tienes un tendedero llamado azotea. Tus tendederos son: patio y terraza.» | Varios Things, caso negativo | PASA |
| 38 | [38-desvincular-uno-de-dos.png](38-desvincular-uno-de-dos.png) | «desvincula mi tendedero» | «¿Cuál quieres desvincular? Tienes patio o terraza.» El JSON muestra `Dialog.ElicitSlot` sobre `DesvincularThingIntent` | RF9 | PASA |
| 39 | [39-ayuda.png](39-ayuda.png) | «ayuda» | Lista de operaciones: vincular, listar, agua, exponer o resguardar, motivo, calibrar, modo, espera y luz. Arriba se ve el final de la desvinculación de la prueba 38: «…tu tendedero se llama terraza» | Ayuda, RF9 | PASA |

**Resultado: 30 de 30 pruebas pasan.**

## Cobertura de requisitos

| Requisito | Pruebas |
|---|---|
| RF4: consulta del sensor | 16, 24, 36 |
| RF5: comandos sobre los actuadores (servo y LED) | 18, 25, 30, 31, 35 |
| RF6: consulta del estado de los actuadores | 17, 32 |
| RF7: vinculación y persistencia | 12, 13, 15, 33 |
| RF8: usuario sin vínculo | 11 |
| RF9: validación, cambio y eliminación del vínculo | 13 (código confirmado), 14 (código no válido), 37, 38, 39 |
| RF14: modo y parámetros, consulta y modificación por voz | 20, 21, 22, 23 |
| §3.1: convivencia de la voz con la lógica automática | 19 (noche, R5), 24 (lluvia, R1), 25 (modo manual) |
| Varios tendederos por usuario | 33 a 38 |
| Calibración desde Alexa | 26 a 29 |
