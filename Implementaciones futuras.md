# Implementaciones futuras del proyecto ASTRA

## Simbología

- ✅ Propuesta hecha con una base.
- ✅✅ Propuesta creada y aprobada por IA.
- ■ Propuesta en proceso de desarrollo.

> **Principio general de integración:** las nuevas implementaciones deben ampliar ASTRA sin romper los flujos que ya están en producción. En especial, mientras Forex se encuentre en calificación Shadow, cualquier mejora de esa rama debe ser de visualización, operación o infraestructura y no modificar modelos, thresholds, targets ni la lógica BUY/SELL/HOLD sin una autorización explícita.

# ESTETICA:

- Grafica mas amplia para el Shadow Forex:

    - La grafica comprender el win/rate general y particular
    
    - Enlista por orden en tabla:
       - orden alfabetico
       - orden de win/rate
       - orden de confidence

# FUNCIONAL:

- Asignacion de modelo IA personalizado con:
    - Maximo 8 modelos IA
    - Memoria de chat compartida
    - Ventana de contexto general

- Estimacion interna de uso de tokens por peticion
    -Conteo por codigo del input del usuario para evitar cortes en el Chat de interaccion

- Modulo de analisis CSV adaptativo para la rama Business
    - Previamente debe verificar el formato de cofificacion (Encoding) del archivo para evitar problemas en el procesamiento sintaxico de los datos
    - Se prepara internamente para cada caso variable de dataset osea, sabe diferenciar si en una columna hay:
        
        - Fechas
        - Timestamps
        - Separadores
        - Campos JSON
        - Strings con info
        - Valores NaN
        - Valores Tipo int
        - Valores con notacion cientifica
        - Campos vacios
        - Lista
        - Diccionario
        - Boleano


# BORRADORES:
