# Estimación del costo mensual (RNF de costo)

Generada con `python tools/estimar_costo.py --libre-lambda 1000000`, con los valores declarados del diseño: 1 tendedero, reporte de respaldo cada 60 s, 20 eventos por día, 10 órdenes de voz por día y el supervisor cada 5 minutos.

```
1 tendedero(s), respaldo cada 60 s, 20 eventos/día

Concepto                            Por mes  Capa gratuita     Uso
IoT: mensajes                        88,500        500,000   17.7%
IoT: operaciones de Shadow           53,040        225,000   23.6%
IoT: reglas disparadas              131,400        250,000   52.6%
IoT: acciones                        88,200        250,000   35.3%
Lambda: invocaciones                 97,140      1,000,000    9.7%
DynamoDB: escrituras                 44,430              —     ver
DynamoDB: lecturas                   18,180              —     ver
```

## Modelo de la cuenta

Captura: [14-capa-gratuita.png](../docs/evidencias/p4/aws/14-capa-gratuita.png) (Billing and Cost Management → Free Tier, 23 de noviembre de 2026).

La cuenta del equipo usa el **plan gratuito con créditos** de AWS: «Your free plan account does not get charged. Credits cover your free plan costs». Al momento de la captura quedaban **USD 139,98** de crédito. Todo uso fuera de las ofertas gratuitas se descuenta de ese saldo, sin cargos a la tarjeta.

## Conclusión

- **Con la capa gratuita clásica**, el consumo de un tendedero queda dentro de los límites en todos los servicios. Lo más alto son las reglas de AWS IoT disparadas, con el 53 % del límite.
- **Con el plan de créditos de esta cuenta**, el costo aproximado con los precios públicos de `us-east-2` es:

| Concepto | Por mes | Precio de referencia | USD por mes |
|---|---|---|---|
| IoT Core: mensajes | 88,500 | 1,00 por millón | 0.088 |
| IoT Core: operaciones de Shadow | 53,040 | 1,25 por millón | 0.066 |
| IoT Core: reglas disparadas | 131,400 | 0,15 por millón | 0.020 |
| IoT Core: acciones | 88,200 | 0,15 por millón | 0.013 |
| Lambda: invocaciones | 97,140 | 0,20 por millón (más la duración, del orden de centavos) | 0.019 |
| DynamoDB: `tendedero_historico` aprovisionada 2/2 | 730 h | 0,00065 por WCU-hora y 0,00013 por RCU-hora | 1.14 (0 si la cubre la oferta siempre gratuita de 25/25) |
| DynamoDB: vinculaciones y dispositivos (bajo demanda) | pocas solicitudes de Alexa | por solicitud | < 0,01 |

  **Total: entre USD 0,21 y 1,37 por mes.** Con USD 139,98 de crédito, el prototipo puede funcionar varios años sin costo. Lo que más pesa es la capacidad aprovisionada del histórico. Si importara el costo, se podría pasar esa tabla a bajo demanda: con unas 44 000 escrituras al mes costaría centavos.

- **Protección:** hay un presupuesto *Zero-Spend* activo ([13-facturacion.jpg](../docs/evidencias/p4/aws/13-facturacion.jpg)), que avisa por correo ante cualquier cargo.
- **Qué cambiaría el costo:** el número de tendederos y la frecuencia de reporte. Con reportes cada 5 s, como en la práctica 3, los mensajes y las reglas se multiplicarían por 12 y saldrían de la capa gratuita clásica. Por eso el respaldo periódico es de 60 s.

Los precios son de referencia, de las páginas públicas de AWS para `us-east-2`. El costo real de cada mes se ve en **Billing and Cost Management → Bills**.
