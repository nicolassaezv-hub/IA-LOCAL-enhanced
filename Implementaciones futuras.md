# Implementaciones futuras del proyecto ASTRA


## Simbologia:

✅ Propuesta hecha con una base

✅✅ Propuesta creada y aprobada por IA

 ■ Propuesta en Proceso de desarrollo


# ESTETICA:

## ✅ Manejo de Procesos multiples simultaneos en la ejecucion (Para Workspace y CLI)

Ver independencia de procesos en base del rendimiento del sistema y que ASTRA se adapte a ello:
Quiero decir, que ASTRA pueda leer la info del sistema en el que corre y diga si puede correr por ejemplo la rama forex y lectura de pdf al mismo tiempo explicandolo ojala de forma numerica (ej: ASTRA puede correr 5 procesos simultaneos como max) y que tambien sea consciente de ello y en caso de llegar a ese limite de procesos tire un mensaje y evite que el usuario haga mas procesos

## ✅ Barra de Personalizacion
La barra de personalizacion (el setting del glow button, color de la interfaz y estilo) debe estar integrada DENTRO de la barra de Configuracion del Workspace, añade un modo Noche (Dark/Light Mode)


# FUNCIONAL:

 ## ✅ Kernel Lab dentro del Prediction Lab

El Prediction Lab debe revisar que el prompt (de prediccion) se cumple usando la variable propuesta y que  se añade Clasificacion Binaria por Kernalizacion si el sistema de prediccion es valido
En el caso que el dataset y el prompt sean validos, se procede con la Clasificacion binaria y la muestra que avalen los resultados (graficos de Kernels, Matriz de confusion y fiabilidad del sistema de prediccion)

## ✅ Seccionar los casos viables del Prediction Lab

Aquellos que pasaron y tienen todo listo tienen una seccion dentro de la barra del Prediction Lab)

## ✅✅ Regla de ASTRA como proyecto de produccion

Tanto Prediction Lab como la rama Forex tratan con datos REALES, en caso de hacer test asegurate usar DATOS reales, no crees datos imaginarios.

## ✅✅ Evolution Engine aplicado a seleccion (Forex,Business,Prediction Lab o en General)

El Evolution Engine esta diseñado para el proyecto ASTRA en general...NO limitado a la rama forex
Se selecciona que rama se quiere evolucionar (por ahora Forex,Chat, Barra de Personalizacion)

## ■ Resaltar código, comandos y rutas de archivo con estilos distintos.

## ■ Pantalla de inicio con animacion

## ✅ Interruptor Modo Automatizacion de Forex y Modo Manual 

Normalmente estara activado el modo Automatizado, de cambiarlo se migran los CSVs a la carpeta del proyecto (Movidos a la carpeta CSVs y los modelos hechos con cache tambien) y se trabaja de forma manual

## ✅✅ Limites y asignacion de RAM + modalidad de rendimiento

Asignacion Min y Max de RAM para ASTRA, una seccion en configuracion que establezca tres funcionalidades:
-Sin limites (pueden usarse desde 0 a la cantidad de gbs de ram necesaria en mi caso 16gb ram)
-Limite asignado (especificar en casillas Min y Max de ram)
-Rendimiento basico


