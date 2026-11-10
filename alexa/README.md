# Skill Tendedero inteligente

El [modelo de interacción es-MX](interaction-model-es-MX.json) contiene la invocación `tendedero inteligente`, los siete intents funcionales del proyecto y los intents integrados de conversación definidos en el archivo.

La Skill utiliza **Custom** y **Provision your own backend resources**. En Build → Endpoint se configura el ARN de la Lambda del equipo. Las pruebas se ejecutaron en Test → Development, con Spanish (MX), mediante entrada textual por la limitación de micrófono observada en el entorno.

## Documentación y evidencias

- [Documentación de Alexa: configuración, vinculación, alias y resultados](../docs/ALEXA.md).
- [Informe técnico consolidado](../docs/INFORME.md).
- [Índice de las 17 capturas](../docs/evidencias/alexa/README.md).
- [Contrato de integración](../docs/CONTRATO.md).
- [Backend Python](../lambda/lambda_function.py).

La vinculación asocia al usuario con un Thing mediante DynamoDB. El cierre de conversación no elimina ese registro. La prueba de cambio válido documenta el paso de `tendedero-prueba2` al Thing físico `tendedero-inteligente`.
