# Primeros pasos

## Instalación

El paquete necesita Python 3.10 o posterior.

```
git clone https://github.com/gabgarar/flinch.git
cd flinch
python -m venv venv
venv/Scripts/python -m pip install -e ".[analysis,dev]"     # Windows
venv/bin/python -m pip install -e ".[analysis,dev]"         # Linux y macOS
```

La distribución se llama `flinch-rv` (el nombre `flinch` está ocupado en PyPI por un paquete
que no tiene relación); el nombre para importar es `flinch`.

| Extra | Añade | Hace falta para |
|---|---|---|
| `analysis` | SciPy, Matplotlib, Astropy | Figuras, forma de las líneas, lectura de los espectros |
| `dev` | pytest | Las pruebas |
| `docs` | mkdocs-material, mkdocstrings, mkdocs-static-i18n | Construir esta web |
| `notebooks` | ipykernel | Cuadernos |

## Las órdenes

Todo se ejecuta con `python -m flinch <orden>`.

| Orden | Qué hace | Tiempo | Descarga |
|---|---|---|---|
| `download` | Todo lo que necesita el análisis de velocidad, es decir, listas, posiciones y flujos minuto a minuto de las fulguraciones (GOES) y las velocidades de NEID y HARPS-N | 3 min | 340 MB |
| `coverage` | Qué fulguraciones ocurrieron mientras NEID observaba | segundos | ninguna |
| `replication` | La medida de la velocidad con NEID y con HARPS-N, y los dos juntos | 20 s | ninguna |
| `robustness` | El resultado de NEID con otras ventanas, fondos y controles | 10 s | ninguna |
| `pilot` | El primer análisis de NEID, con la potencia de las oscilaciones | 10 s | ninguna |
| `numbers` | Los recuentos y los números descriptivos del texto | 5 s | ninguna |
| `spectra` | Extractos de cada espectro de una ventana de tiempo | 10 s por espectro | 113 MB por espectro |
| `campaign` | `spectra` desatendido para las fulguraciones más intensas, o para sus ventanas de control | horas | 113 MB por espectro |
| `paper-spectra` | Exactamente los 1296 espectros del artículo, cada uno comprobado con su huella | 3 horas o más | 143 GB |
| `chromosphere` | Respuesta de los índices espectrales a las fulguraciones con espectros | 1 min | ninguna |
| `paper-figures` | Las figuras del artículo, en PDF con estilo de revista | 20 s | ninguna |
| `verify` | Cada número del artículo frente a las tablas de `results/` | segundos | ninguna |
| `reproduce` | Todo lo anterior en orden, con un informe de lo que coincide (véase [Reproducir el artículo](reproduce.md)) | 10 min | 340 MB, o 143 GB más con los espectros |

Una primera sesión:

```
python -m flinch download
python -m flinch coverage
python -m flinch replication
python -m pytest
```

## Dónde van los datos

Las descargas van a `data/` dentro del repositorio, o a la carpeta que indique la variable de
entorno `FLINCH_DATA`. Las tablas van a `results/`, o a la carpeta que indique
`FLINCH_RESULTS`, y las figuras a `docs/web/img/`. `reproduce` lo escribe todo en
`reproduction/` y deja el repositorio como estaba.

Las fulguraciones y las observaciones posteriores al 12 de noviembre de 2026 se ignoran,
para que una descarga posterior dé la misma muestra
([por qué](reproduce.md#que-se-ha-fijado-y-como)).

!!! warning "Los espectros pesan mucho"
    Un espectro de nivel 2 de NEID ocupa 113 MB y el archivo no sirve rangos de bytes, así que
    cada uno se descarga entero, se reduce a un extracto de 0,2 MB y se borra. Los 1296
    espectros del artículo mueven 143 GB por la red y conservan 260 MB. El ordenador tiene
    que seguir despierto: en un portátil, déjalo enchufado y con la tapa abierta.

## Pruebas

```
python -m pytest
```

Las pruebas usan datos sintéticos y no tocan la red.
