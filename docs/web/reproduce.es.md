# Reproducir el artículo

Una sola orden descarga los datos públicos, ejecuta todo el análisis, compara cada tabla con
la que guarda el repositorio y comprueba cada número del artículo con las tablas nuevas.

```
python -m flinch reproduce
```

Necesita 340 MB de descargas y unos diez minutos. Deja fuera los espectros, que son 143 GB;
los niveles de más abajo explican cómo incluirlos. No se modifica nada del repositorio. Las
tablas nuevas, las figuras, la salida de cada paso y un informe van a `reproduction/`.

!!! note "Desde el 24 de noviembre de 2026"
    La NOAA ha reeditado los ficheros de GOES, así que una descarga hecha ahora ya no es la
    del artículo. La orden sigue encontrando de acuerdo los 255 números del artículo, pero
    da dos datos de entrada como `different` y cinco tablas como `DIFFERENT`, y su última
    línea es `Not fully reproduced`. [La reedición de los ficheros de GOES](#goes-reissue)
    cuenta qué cambió y cómo obtener exactamente las tablas del artículo.

## Desde cero

```
git clone https://github.com/gabgarar/flinch.git
cd flinch
python -m venv venv
venv/Scripts/python -m pip install -r requirements-lock.txt     # las versiones exactas que se usaron
venv/Scripts/python -m pip install --no-deps -e .
venv/Scripts/python -m flinch reproduce
```

En Linux y macOS el intérprete es `venv/bin/python`. El artículo se calculó con Python 3.14
en Windows 11. Sin la primera línea de `pip`, `pip install -e ".[analysis,dev]"` instala las
versiones actuales, que sirven para usar el paquete pero no son la misma prueba.

## Cuatro niveles

Cada nivel añade una descarga al anterior.

| Nivel | Orden | Descarga | Tiempo | Qué demuestra |
|---|---|---|---|---|
| 0 | `python -m flinch verify` | ninguna | segundos | Los números del artículo son los de las tablas del repositorio |
| 1 | `python -m flinch reproduce` | 340 MB | 10 min | Los archivos públicos y este código vuelven a dar las 14 tablas de velocidad |
| 2 | `python -m flinch reproduce --spectra sample` | 1,1 GB más | 5 min más | Diez espectros del artículo, elegidos al azar, siguen siendo los mismos en el archivo |
| 3 | `python -m flinch reproduce --spectra all` | 143 GB más | 3 horas o más | También las tablas espectrales, es decir, las Tablas 2 y B.1 y la Fig. 4 del artículo |

`--sample 30` cambia el número de espectros del nivel 2. `--no-download` usa los datos que ya
están en disco. `--out` indica otra carpeta para la salida. Una ejecución interrumpida puede
lanzarse de nuevo, y lo que ya está en disco no se descarga otra vez.

## El informe

`reproduction/report.txt` tiene seis partes.

1. **Datos.** Cada dato de entrada se compara con el que se usó en el artículo mediante una
   huella (SHA-256) de lo que el análisis lee de él. `identical` significa que el archivo
   sigue sirviendo los mismos datos.
2. **Análisis de velocidad.** Una línea por orden, con el tiempo que tardó y el fichero que
   guarda su salida.
3. **Espectros.** Cuántos extractos son idénticos a los del artículo, y si se repitió el
   análisis espectral.
4. **Figuras.** Las figuras del artículo, en PDF, en `reproduction/figures/`.
5. **Tablas.** Cada tabla nueva frente a la del repositorio. `identical` es el mismo texto.
   `same numbers` significa que todos los números coinciden en nueve cifras significativas,
   que es lo que puede cambiar otro procesador u otra versión de una biblioteca. La
   respuesta de los espectros está escrita en partes por mil o por millón de cada magnitud,
   y ahí las nueve cifras son las de la magnitud. `DIFFERENT` nombra las columnas que
   difieren y en cuánto.
6. **Números del artículo.** Los 255 números del texto y de las tablas del artículo, cada
   uno frente a las tablas nuevas. Un número pasa cuando el artículo da un redondeo correcto
   de él.

La última línea es `Reproduced.` cuando ningún paso falló, ninguna tabla difiere y todos los
números coinciden. La orden termina entonces con código 0, y con 1 en caso contrario.

`results/paper_check.csv` lista los 255 números con el lugar del artículo donde aparece cada
uno, tal como los dejó la última ejecución de `verify`.

## Lo que se ejecutó para el artículo

Los días 21 y 22 de noviembre de 2026 se descargó todo de nuevo en una carpeta vacía y se
ejecutó desde un clon recién hecho, con las versiones de `requirements-lock.txt`.

| Qué | Resultado |
|---|---|
| Datos de entrada del análisis de velocidad (12 ficheros) | idénticos, 12 de 12 |
| Tablas de velocidad (14) | idénticas, byte a byte |
| Espectros (1296 ficheros, 143 GB) | idénticos, 1296 de 1296 |
| Tablas espectrales (2) | idénticas, byte a byte |
| Números del artículo (243) | 243 de 243 coinciden |
| Figuras del artículo (5) | las mismas imágenes, píxel a píxel |

La comprobación encontró dos números que se habían redondeado dos veces en el texto. La
dispersión de los cambios de velocidad de las fulguraciones de HARPS-N es de 0,40 m/s, no de
0,41, y el exceso del Apéndice C es de 0,43 ± 0,10 m/s, no de 0,44 ± 0,11. Los dos están
corregidos.

El 22 de noviembre de 2026 se ejecutó en Linux de dos maneras. El flujo `reproduce` del
repositorio lo ejecutó en GitHub desde los archivos públicos, con diez espectros de la
muestra, en seis minutos. Los 12 datos de entrada y los diez extractos son idénticos. En
Ubuntu 24.04 con Python 3.12 se ejecutó el análisis entero, incluida la parte espectral, con
los 1296 extractos. En las dos, los 243 números coinciden y todas las tablas tienen los
mismos números. La mayor diferencia está en la undécima cifra significativa. Las cinco
figuras dibujadas en Linux son las mismas imágenes que las del artículo.

La ejecución en Linux encontró un defecto, ya corregido. La profundidad y la anchura de la
línea media salen de un ajuste iterativo, que se detenía a unas centésimas de parte por
millón de su mínimo, en un punto que dependía de la máquina. Las dos máquinas diferían
hasta en 0,0001 ppm en esas dos columnas de `spectral_response.csv`, y la orden daba la
tabla por `DIFFERENT`. El ajuste se lleva ahora hasta la convergencia, y las dos máquinas
coinciden hasta las últimas cifras que conserva la aritmética. El cambio movió esas dos
columnas menos de 0,0001 ppm, frente a errores de 50 a 80 ppm, así que
`spectral_response.csv` ya no es byte a byte la tabla de la primera ejecución. No cambió
ningún número del artículo ni ninguna figura. Ejecutado de nuevo en Windows con el ajuste
corregido, las 16 tablas son idénticas a las del repositorio. Los espectros no se
descargaron por segunda vez, porque los extractos son los mismos ficheros.

El 23 de noviembre de 2026 una última revisión del artículo añadió doce números, y la orden
comprueba ahora 255. Son la medida sin las fulguraciones que empiezan poco después de otra
(cuatro filas nuevas en `cleaning_variants.csv`), el número de controles de una fulguración
y lo que el artículo deduce del aumento de brillo de las fulguraciones en luz visible. La
misma revisión hizo que la probabilidad de detectar un desplazamiento use el desplazamiento
tal como se recupera, como ya hacían las inyecciones de NEID, y ese número del artículo pasó
del 99 al 98 %. Ejecutado de nuevo en Windows con los datos en disco, las 16 tablas son
idénticas a las del repositorio y los 255 números coinciden.

El 24 de noviembre de 2026, el día en que se envió el artículo, se comprobó la versión 1.0.0
tal como está archivada en Zenodo. El archivo es idéntico, fichero a fichero, a la etiqueta
del repositorio. Instalado desde él en una carpeta vacía, pasan las 122 pruebas y los 255
números coinciden. En Ubuntu 24.04 con Python 3.12 el análisis entero con los datos del
artículo, incluida la parte espectral, termina con `Reproduced.` y todas las tablas tienen
los mismos números. En Windows, con la copia congelada de los datos, las 16 tablas son
idénticas a las del repositorio. Una descarga de los archivos públicos hecha ese día ya no
dio los datos de entrada del artículo, porque la NOAA había reeditado los ficheros de GOES.
Lo describe [La reedición de los ficheros de GOES](#goes-reissue).

## Paso a paso

`reproduce` ejecuta estas órdenes en este orden. Cada una puede ejecutarse sola, y entonces
escribe en `results/`.

```
python -m flinch download
python -m flinch coverage
python -m flinch replication
python -m flinch replication --cleaning
python -m flinch robustness
python -m flinch pilot
python -m flinch numbers
python -m flinch paper-spectra
python -m flinch chromosphere
python -m flinch paper-figures --out figures
python -m flinch verify
```

| Salida | La genera | Contenido |
|---|---|---|
| `results/flare_sample.csv` | `coverage` | Las 2122 fulguraciones M y X y su cobertura por NEID |
| `results/velocity_by_instrument.csv` | `replication` | Cambio medio, desplazamiento de una X1 y término de rotación, por clase y por instrumento, y los dos juntos (Tabla 1) |
| `results/replication_events.csv` | `replication` | Cada fulguración y cada control de los dos instrumentos, con su cambio de velocidad (Fig. 3) |
| `results/replication_profiles.csv` | `replication` | Velocidad media alrededor del máximo en intervalos de 10 minutos (Fig. 2) |
| `results/early_window.csv` | `replication` | Velocidad media de 60 a 50 minutos antes del máximo, por clase y por instrumento (Apéndice C) |
| `results/cleaning_variants.csv` | `replication --cleaning` | El cambio medio y el término de rotación con otros umbrales para descartar días y, en HARPS-N, con el indicador de calidad por encima de 0,9 |
| `results/robustness.csv` | `robustness` | La tabla de variantes con NEID (Tabla A.1) |
| `results/injections.csv` | `robustness` | Un desplazamiento añadido y medido después con NEID (Apéndice A) |
| `results/pilot_*.csv` | `pilot` | El primer análisis de NEID, con la potencia de las oscilaciones |
| `results/text_numbers.csv` | `numbers` | Los recuentos y los números descriptivos del texto, es decir, velocidades y días, lo que quitan los cortes, las pruebas de muestra representativa, la frecuencia de las fulguraciones y el tiempo que ocupan |
| `data/spectra/` | `paper-spectra` | Los extractos de los 1296 espectros del artículo, cada uno comprobado con su huella |
| `results/spectral_response.csv` | `chromosphere` | Respuesta de cada fulguración y cada control, con sus errores (Tabla B.1) |
| `results/spectral_indices.csv` | `chromosphere` | Resumen de cada índice por banda de clase (Tabla 2) |
| Ficheros PDF | `paper-figures` | El ejemplo del método, la velocidad media alrededor del máximo, el cambio de cada fulguración frente a su clase y su posición, y la respuesta media de los espectros |
| `results/paper_check.csv` | `verify` | Cada número del artículo frente a las tablas |

Tres variables de entorno cambian dónde va cada cosa. `FLINCH_DATA` es la carpeta de las
descargas (`data/` si no se indica), `FLINCH_RESULTS` la de las tablas (`results/`) y
`FLINCH_DATA_END` el último día de datos (véase más abajo).

## Qué se ha fijado, y cómo

Cuatro cosas hacían que los resultados dependieran del día y de la máquina. Ahora están
fijadas en el código.

- **El último día de datos.** La tabla de NEID crece cada día despejado y las listas de GOES
  se reeditan con una fecha final posterior, así que una descarga posterior tenía más
  fulguraciones, más observaciones y otros controles. `DATA_END`, en `flinch/config.py`, es
  el 13 de noviembre de 2026. Las fulguraciones y las observaciones de ese día en adelante se
  ignoran, contenga lo que contenga la descarga. La última observación de NEID del artículo
  es del 12 de noviembre de 2026.
- **Los espectros.** Se descargaron con `campaign`, que recorre las fulguraciones de mayor a
  menor hasta agotar un presupuesto de horas y de ficheros. Lo que descarga depende de la
  conexión y del día. `flinch/reference/spectra_files.csv` lista los 1296 ficheros que
  descargó para el artículo, con la huella de cada extracto, y `paper-spectra` descarga
  exactamente esos.
- **Las elecciones al azar.** Los controles y el remuestreo usan una semilla fija.
- **Los números del texto.** Los recuentos, porcentajes y pruebas que no estaban en ninguna
  tabla los escribe ahora `numbers`.

## Límites

Lo que sigue todavía puede hacer que una reproducción difiera, o la encarece.

- **Los archivos pueden cambiar los datos.** NEID puede reprocesar sus espectros con una
  versión más nueva de su programa de reducción (los 1296 usados aquí son todos de la
  versión 1.5.3), y la NOAA reedita los ficheros de GOES, como hizo en noviembre de 2026. Las
  huellas no impiden un cambio, pero lo detectan. El informe dice entonces qué dato es
  `different`, y una tabla que difiere tiene explicación. Una copia congelada de los ficheros
  de GOES, de la tabla de NEID y de los extractos de los 1296 espectros, tal como estaban
  cuando se calculó el artículo, va adjunta a la
  [versión 1.0.0](https://github.com/gabgarar/flinch/releases/tag/v1.0.0) del repositorio
  (`flinch-data.zip`, 556 MB). [La reedición de los ficheros de GOES](#goes-reissue) explica
  cómo repetir el artículo con ella, sin los 143 GB.
- **Los espectros son 143 GB.** Un fichero de nivel 2 ocupa 113 MB y el archivo no sirve
  partes de un fichero, así que cada uno se descarga entero, se reduce a un extracto de
  0,2 MB y se borra. Los 1296 ficheros tardaron aquí 3 horas y 14 minutos, a 12 MB por
  segundo, que son 9 segundos por fichero. Una línea más lenta necesita más en proporción.
  Necesitan 400 MB de disco libre a la vez y dejan 260 MB de extractos. Una conexión
  doméstica puede frenarse tras decenas de GB. En la primera campaña cayó a una décima
  parte de su velocidad después de 100 GB. En esta segunda descarga no ocurrió. El
  ordenador tiene que seguir despierto, así que un portátil debe estar enchufado y no
  suspenderse al cerrar la tapa. El nivel 2 es la alternativa barata. No repite el análisis
  espectral, pero demuestra que el archivo y la extracción siguen dando los mismos
  extractos.
- **Algunos espectros no se pueden leer.** En 51 exposiciones de dos ventanas (27 de la
  fulguración X1.3 del 4 de julio de 2026 y 24 del control de la X4.9 del 31 de diciembre de
  2023) el archivo sirve ficheros sin el espectro unido. No están en la lista, y esas dos
  ventanas tienen menos espectros que las demás. Esa fulguración y ese control no están
  entre los utilizables.
- **La elección de los espectros no se repite.** La lista recoge qué espectros se
  descargaron, no una regla que vuelva a darlos. Las ventanas son las 20 fulguraciones de
  clase X que NEID observó en el máximo o durante la subida, las mismas horas del día sin
  fulguraciones más próximo para 14 de ellas, y las 11 de las 25 fulguraciones entre M5 y M9
  que tuvieron cielo despejado y estable. Dentro de una ventana se tomaron todos los
  espectros cercanos a la fulguración y uno de cada dos o tres más lejos. Ejecutar `campaign`
  otra vez no daría los mismos ficheros, porque su presupuesto cortó la última ventana y las
  dos ventanas de arriba perdieron espectros.
- **Versiones de los programas y máquinas.** Con las versiones de `requirements-lock.txt`
  en Windows 11 las tablas salen idénticas, byte a byte. En Linux las mismas versiones dan
  los mismos números hasta once cifras significativas, pero no el mismo texto, porque otro
  procesador y otras bibliotecas matemáticas redondean de otra manera las últimas cifras.
  Por eso las tablas se comparan número a número, y no solo como texto, y el informe dice
  `same numbers`. En Linux la extracción se comprobó con diez espectros tomados del
  archivo, y el análisis espectral con los 1296 extractos hechos en Windows. La descarga de
  los 143 GB no se ha repetido allí. En macOS no se ha probado. NumPy no promete los mismos
  números aleatorios en todas sus versiones futuras. Si cambiaran, los controles elegidos y
  los errores del remuestreo cambiarían en sus últimas cifras.
- **La orden no compara las figuras.** Se dibujan de nuevo a partir de las tablas nuevas.
  En las ejecuciones descritas arriba, en Windows y en Linux, se convirtieron en imágenes y
  se compararon con las del artículo, y las cinco son iguales píxel a píxel. Con otras
  versiones de Matplotlib o con otros tipos de letra pueden diferir en detalles que no
  cambian lo que muestran.
- **Los números tomados de otros artículos** (el aumento de brillo de dos fulguraciones en
  luz visible y el factor de la escala antigua de GOES) están escritos en `flinch/verify.py`
  tal como se leyeron en esos artículos. Lo que el artículo deduce de ellos se comprueba. La
  orden no lee los propios artículos.

## La reedición de los ficheros de GOES { #goes-reissue }

Entre el 22 y el 24 de noviembre de 2026 la NOAA reeditó los ficheros de GOES que usa el
artículo. La descarga del 21 y el 22 de noviembre todavía dio los ficheros del artículo. Una
descarga hecha desde entonces ya no los da.

Cambiaron cuatro cosas, hasta el último día de datos del artículo.

- **La lista de fulguraciones es la misma.** Tiene las mismas 2187 fulguraciones de clase M
  y X, con las mismas horas y clases.
- **La longitud y la latitud heliográficas de las fulguraciones se movieron 180 grados**, en
  unas 1960 de ellas. En los ficheros anteriores la mayoría de las latitudes caía fuera del
  intervalo de −90 a 90 grados, y en los reeditados no lo hace ninguna, así que los valores
  anteriores eran erróneos. El análisis no depende de ellos. Usa la posición en el disco, la
  longitud de Carrington y diferencias de latitud. Las columnas `lon` y `lat` de
  `results/flare_sample.csv` y `results/pilot_flares.csv` vienen de los ficheros anteriores
  y no deben usarse como coordenadas heliográficas.
- **Los flujos de rayos X por minuto de GOES-18** entre el 9 de octubre y el 11 de noviembre
  de 2026 cambiaron hasta un 14 %.
- **El flujo máximo y la fluencia** de una docena de fulguraciones cambiaron en unas pocas
  partes por millón.

Esto es lo que da `python -m flinch reproduce` con una descarga del 24 de noviembre de 2026.

| Qué | Resultado |
|---|---|
| Datos de entrada del análisis de velocidad (12 ficheros) | 10 idénticos. La lista de fulguraciones M y X de GOES y los flujos por minuto de GOES-18 de 2026 son `different` |
| Tablas de velocidad (14) | 9 idénticas o con los mismos números. 5 son `DIFFERENT` |
| Números del artículo (255) | 255 de 255 coinciden |
| Figuras del análisis de velocidad (3) | las mismas imágenes, píxel a píxel |
| Última línea | `Not fully reproduced`, y la orden termina con código 1 |

De las cinco tablas que difieren, `flare_sample.csv` y `pilot_flares.csv` lo hacen en las
columnas `lon` y `lat` y, en menos de una parte en 100 000, en la fluencia y la posición de
unas pocas fulguraciones. `velocity_by_instrument.csv` y `robustness.csv` difieren en
0,000000002 m/s como mucho, en el término de rotación y en el desplazamiento de una
fulguración X1, y `pilot_tests.csv` en otro tanto en un estadístico de contraste.

Para obtener exactamente las tablas del artículo hay que usar la copia congelada. Se
descomprime `flinch-data.zip` en la carpeta del código, lo que da `data/`. Después se
descarga solo la serie de HARPS-N, que es una publicación fija con DOI y no se copia, y se
ejecuta el análisis con lo que hay en disco.

```
python -c "from flinch import harpsn; harpsn.download_series()"
python -m flinch reproduce --no-download --spectra all
```

No hay que ejecutar `python -m flinch download` en esa carpeta. Desde la reedición descarga
también las listas nuevas de fulguraciones de GOES-18, cuyos nombres de fichero llevan una
fecha final posterior, y el código lee la lista más reciente que encuentra en `data/goes/`.
Las versiones anteriores de esta página recomendaban esa orden. Ejecutado así el 24 de
noviembre de 2026, con la versión 1.0.0 tal como está archivada en Zenodo, las 16 tablas son
idénticas a las del repositorio y la última línea es `Reproduced.`

## Pruebas

```
python -m pytest              # 122 pruebas con datos sintéticos, sin red, un minuto
python -m pytest -m network   # 2 pruebas que comprueban que los archivos siguen respondiendo como espera el código
```

Otras tres pruebas comparan las descargas reales con las tablas del repositorio. Se ejecutan
cuando los datos están en disco.
