# ASTRA

# Peticiones Personales

- Actualiza constantemente

- Sigue avanzando con la rama forex, consigue como minimo:

  - Integrar informe automatico en primera iteracion entre la rama forex y el servidor de flujo automatizado

- Configura el servidor VM a usar, aplica tests end-end para verificar viabilidad y finalizar la consolidacion del proyecto (Version Final)

- Usa herramientas para avanzar

   - ### Base44 (Integracion y testeo)
   - ### Replit (Integracion y planificacion)
   - ### Bolt.new (solo para crear borrador)
   - ### Lovable (Integracion y Planificacion)
   - ### Github Copilot (Diagnostico y Planificacion)
   - ### Claude (solo de diagnostico)
   - ### Codex CLI/Chatgpt (Integracion y testeo)

- Para comprobaciones de calidad de usuario (UX) o estetica consulta con Base44, asegurate de mencionar que la estetica es propia del Workspace en servidor (modificar HTML constantemente)
  
[Ir a integrar las nuevas implemetaciones listadas](Implementaciones%20futuras.md) una vez completado los test End-to-End de produccion

## Informacion General

Este Workflow IA esta hecha a partir de aportes de Nicolas Saez Valenzuela, Replit, Copilot, Chatgpt entre otros servicios digitales con tal de brindar una experiencia mas completa y complementada por modulos extensos con tal de concentrar una learning AI con fijacion en procesamiento de archivos y analisis intensivo de datasets del area del mercado FOREX (Divisas y Materias Primas).

Todo, en base a un sistema local PC de las siguientes especificaciones

PROCESADOR:

- Intel(R) Core (TM) I5-10300H CPU @2.5GHz

RAM:

- 16GB RAM

Se le asigna un máximo de 10GB de RAM a la IA

GPU:

- NVIDIA 1650ti 8GB VRAM 

# API

## Actualmente el funcionamiento de esta IA es gracias a la conexion por GroqCloud

-  name: NICO'S LOCAL AI

-  ID: "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"

-  model= "openai/gpt-oss-120"

  # Configuracion VM
  
Para automatizar la rama FOREX y el display grafico se logro migrar el Workspace a una VM (Virtual Machine) para optimizar tiempos de ejecucion del Pipeline

En la comparativa practica se demostro que la "prediccion completa" de un solo simbolo tomaba entre 7-15 minutos, hubo una rebaja a 9 minutos usando una implementacion caché.

Sin embargo no es una optimizacion acertada al sistema completo si tomamos en cuenta que en hay mas de 80 Simbolos (Divisa,Commodities y Cripto)

- ### HASTA EL MOMENTO SOLO HAY TESTS. NINGUNA ACTIVIDAD 24/7 (Scheduler,Rolling Dataset y Watcher desactivados) HASTA COMPROBAR LA FIABILIDAD PRODUCTIVA

  ## Imagen: Ubuntu 24.04
  
  ## Sistema Operativo: Canonical Ubuntu
  
  ## Memoria: 12GB RAM
  
  ## Almacenamiento: 57 GB
  
# POR ACTUALIZAR!!!!!
# Estructura

Esta IA Local se compone de mas de 200 codigos Python para asegurar eficiencia y rapidez en la ejecucion.
El programa puente (main.py) viene siendo la central de los comandos ingresados para ser rediregido a funciones/herramientas de utilidad.

Se incluyen 5 codigos adicionales para verificar la integridad de los modulos presentes en cada codigo Python.

- check_startup

- check_skeleton

- check_pipeline


Notese que se necesita activar un entorno virtual (activate.bat) antes de ejecutar el main.

A continuacion se dan las caracteristicas y detalles del programa principal mas los anexos.

# Comandos y Programa Puente (main.py + .env)
### Comandos

El nucleo del esqueleto organiza las entradas del usuario y repone todo en una funcion general, en esta funcion principal estan seccionados los comandos 

<details>
<summary>Ver comandos</summary>


## CSVs Disponibles para Analisis y Prediccion Forex

 (UPDATED 23/06/2026) https://drive.google.com/drive/folders/16K6FPgHz6k_FQ6SBYFvOv-7XwaQXsRLm?usp=sharing
 
## Modulos (Instalados y/o Integrados)

Aqui el archivo con el listado de modulos Instalados e Integrados
 https://docs.google.com/spreadsheets/d/1I2JpcZ6_V_WUdXkkYkP7MZ1fgQcPW6y73xBbtZjOfHI/edit?usp=sharing

## Actualizacion de Modulos (Semanal)
## Ejemplos de Ejecucion con Dataset

