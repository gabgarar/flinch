# flinch

Fulguraciones solares en la velocidad radial del Sol como estrella.
(cambios inducidos por fulguraciones en la velocidad radial del Sol como estrella).

*¿Contaminan las fulguraciones solares la detección de análogos terrestres por velocidad radial?*

Para encontrar un planeta como la Tierra alrededor de una estrella como el Sol hay que medir
la velocidad de la estrella con una precisión de unos 10 cm/s: la Tierra mueve el Sol 9 cm/s.
Algunos de los espectrógrafos construidos para eso observan también el Sol cada día despejado,
como si fuera una estrella lejana. Este proyecto cruza esas velocidades solares con las fulguraciones
registradas por los satélites GOES y pregunta:

1. ¿Mueve una fulguración la velocidad radial del Sol visto como estrella?
2. ¿A partir de qué tamaño de fulguración, y cuánto?
3. ¿Qué significa eso para la búsqueda de planetas?

Usa dos instrumentos que miran el Sol a horas distintas y por tanto ven fulguraciones
distintas: NEID (Arizona) y HARPS-N (La Palma).

## La respuesta

Las fulguraciones solares no contaminan significativamente la detección de análogos terrestres
por velocidad radial. Esto se ha demostrado para el Sol, no para las estrellas de tipo solar en
general.

| Pregunta | Respuesta | Prueba |
|---|---|---|
| ¿Cambia la velocidad durante una fulguración? | No, dentro de 7 cm/s | 254 medidas de 253 fulguraciones de clase M y X: −0,029 ± 0,026 m/s. Solo NEID: −0,035 ± 0,035 (139). Solo HARPS-N: −0,021 ± 0,039 (115) |
| ¿La mueven más las fulguraciones mayores? | No | 18 fulguraciones de clase X: −0,074 ± 0,072 m/s. Ningún cambio, pero la cota, 0,2 m/s, es el doble de la señal de la Tierra |
| ¿Hay firma de rotación (signo opuesto al este y al oeste)? | No | −0,006 ± 0,038 m/s para una X1 en el limbo, a un factor entre 1,6 y 3,5 del mayor desplazamiento esperado |
| ¿Se habría visto una señal? | Sí | Se recupera el 98 % de un desplazamiento añadido a los datos |
| ¿Ven los espectros las fulguraciones? | Sí | Ca II H y K y H alfa se abrillantan en las 14 fulguraciones del disco con espectros, entre 2 y 5 partes por mil |
| ¿Cuánto tiempo pasa el Sol en fulguración? | El 1,6 % | 358 fulguraciones de clase M o X al año de media entre 2020 y 2026, contadas de inicio a final (19 minutos en la mediana); el 3,8 % en 2024, el año más activo |

El Sol no se inmuta, pero se sonroja: las líneas cromosféricas se abrillantan mientras la
velocidad no se mueve. Véase [Resultados](results.md).

![Velocidad media alrededor del máximo de la fulguración, NEID y HARPS-N](img/two_instruments_profiles.png)

## Qué hay en esta documentación

| Página | Contenido |
|---|---|
| [Primeros pasos](getting-started.md) | Instalación y órdenes |
| [Fulguraciones de GOES](data/goes.md) | Las listas de fulguraciones: qué contienen, un ejemplo y cómo se procesan |
| [Velocidades de NEID](data/neid-velocities.md) | La tabla de velocidades: columnas, cortes de calidad, tendencia diaria |
| [Espectros de NEID](data/neid-spectra.md) | Los espectros: qué se extrae de cada archivo de 113 MB |
| [Velocidades de HARPS-N](data/harpsn.md) | El segundo instrumento: qué es y cómo se procesa |
| [Método](method.md) | La medida en cuatro pasos |
| [Resultados](results.md) | Tablas y figuras |
| [Reproducir el artículo](reproduce.md) | Una orden que lo ejecuta todo y comprueba el artículo; qué cuesta cada paso; qué puede diferir todavía |

Todos los datos son públicos y no necesitan registro. La web está en español y en inglés: usa
el botón de idioma de la parte superior. Los rótulos de las figuras y la referencia de la API
están en inglés.
