# Diagramas preliminares (revisar con implementación real)

## Arquitectura del sistema

```mermaid
flowchart LR
    A[Usuario] --> B[Skill Alexa]
    B --> C[AWS Lambda]
    C <--> D[(DynamoDB bindings)]
    C <--> E[(IoT Shadow)]
    F[Sensor MH] --> G[ESP32]
    E <--> G
    G --> H[Servo cubierta]
```

## Secuencia: vinculación

```mermaid
sequenceDiagram
    actor U as Usuario
    participant X as Alexa
    participant L as Lambda
    participant I as IoT Registry
    participant D as DynamoDB
    U->>X: Vincular Thing
    X->>L: Intent + slot + userId
    L->>I: DescribeThing(thingName)
    I-->>L: Existe / error
    alt Existe
        L->>D: PutItem(userId, thingName)
        D-->>L: Guardado
        L-->>X: Vinculado
    else No existe
        L-->>X: Solicitar identificador valido
    end
    X-->>U: Respuesta en espanol
```

## Secuencia: consulta del sensor

```mermaid
sequenceDiagram
    actor U as Usuario
    participant X as Alexa
    participant L as Lambda
    participant D as DynamoDB
    participant S as IoT Shadow
    U->>X: Hay agua?
    X->>L: ConsultarAgua + userId
    L->>D: GetItem(userId)
    D-->>L: thingName
    alt Vinculado
        L->>S: GetThingShadow(thingName)
        S-->>L: state.reported.agua_detectada
        L-->>X: Respuesta sobre sensor
    else No vinculado
        L-->>X: Pedir vincular
    end
    X-->>U: Voz / texto
```

## Secuencia: comando al servo

```mermaid
sequenceDiagram
    actor U as Usuario
    participant X as Alexa
    participant L as Lambda
    participant D as DynamoDB
    participant S as IoT Shadow
    participant E as ESP32
    U->>X: Cierra la cubierta
    X->>L: CerrarCubierta + userId
    L->>D: GetItem(userId)
    D-->>L: thingName
    L->>S: Update desired.cubierta
    S-->>L: Actualizacion aceptada
    L-->>X: He solicitado cerrar
    S-->>E: update/delta
    E->>E: Movimiento servo
    E->>S: update reported.cubierta
    X-->>U: Respuesta
```

## Clases del ESP32

```mermaid
classDiagram
    class SensorAgua {
      +iniciar()
      +leerRaw() int
      +detectar(raw, estado, umbralSeco, umbralAgua) bool
    }
    class ServoCubierta {
      +iniciar() bool
      +solicitar(posicion, ahora)
      +estimada(ahora) Posicion
    }
    class ClienteShadow {
      +iniciar(endpoint, thing, ca, certificado, clave) bool
      +atender(ahora, servo)
      +reportar(ahora, raw, agua, cubierta)
    }
    class Tendedero
    Tendedero --> SensorAgua
    Tendedero --> ServoCubierta
    Tendedero --> ClienteShadow
    ClienteShadow --> ServoCubierta : aplica desired
```

`Tendedero` representa el módulo que coordina las tres clases.

## Clases de Lambda

```mermaid
classDiagram
    class BindingRepository {
      +find(user_id)
      +bind(user_id, thing_name)
      +unbind(user_id)
    }
    class ShadowService {
      +assert_thing_exists(thing_name)
      +read(thing_name)
      +request_cover(thing_name, position)
    }
    class VincularHandler
    class DesvincularHandler
    class ComandoCubiertaHandler
    class ConsultarAguaHandler
    class ConsultarCubiertaHandler
    VincularHandler --> BindingRepository
    VincularHandler --> ShadowService
    DesvincularHandler --> BindingRepository
    ComandoCubiertaHandler --> BindingRepository
    ComandoCubiertaHandler --> ShadowService
    ConsultarAguaHandler --> BindingRepository
    ConsultarAguaHandler --> ShadowService
    ConsultarCubiertaHandler --> BindingRepository
    ConsultarCubiertaHandler --> ShadowService
```

## Circuito previsto

```mermaid
flowchart LR
    USB[USB de datos y alimentación] --> MCU[ESP32]
    MCU -- 3V3 --> MH[Sensor MH]
    MH -- S a GPIO34 / ADC1 --> MCU
    MH --- GND[Tierra común]
    MCU --- GND
    MCU -. GPIO26 PWM, pendiente de validar nivel .-> S[Servo, etiqueta MG90S informada]
    F[Fuente DC regulada por verificar] -- Positivo --> S
    F --- GND
    S --- GND
```

El diagrama identifica las conexiones previstas. Completar con foto y características de la fuente cuando se verifique la unidad física.
