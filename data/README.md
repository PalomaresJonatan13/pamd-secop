# Datos

Esta carpeta no guarda datos en Git (ver `.gitignore`). Los datos son los procesos de contratación de SECOP II del portal de datos abiertos datos.gov.co ([dataset SECOP II](https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II/a8sx-pfr3/about_data)), descargados el **2 de septiembre de 2026**. Vienen en un `.zip` de unos 1,7 GB que, descomprimido, pesa varios GB. Spark no lee archivos `.zip`, así que hay que descomprimirlo antes de cargarlo.

1. Descarga el `.zip` desde [Google Drive](https://drive.google.com/file/d/1S-0hBc4gr9rwaRi_cEMqCO7G80qV-fHv/view?usp=drive_link) (no está en el repositorio por su tamaño) y guárdalo en esta carpeta (`data/`).
2. Descomprímelo dentro de `data/`. En Windows (PowerShell): `Expand-Archive -Path data\<archivo>.zip -DestinationPath data`. Debe quedar un `.csv` directamente en `data/`.
3. Desde la raíz del repositorio, con el entorno levantado (`docker compose up -d`), cópialo a MinIO: `docker compose run --rm minio-load`. Tarda según el tamaño y termina listando el archivo en `s3a://rawdata/secop/`; su tamaño debe coincidir con el del CSV en tu disco. Si prefieres, también puedes subirlo a mano desde la consola (http://localhost:9002) al bucket `rawdata`, carpeta `secop/`.
4. En el notebook `01`, pon `RECONSTRUIR_BRONZE = True` y ejecútalo para crear el bronze (ver README principal).

Si el enlace de Drive no está disponible para quien lo necesite, el dataset original se puede volver a descargar desde datos.gov.co (el contenido cambia con el tiempo, así que no será idéntico al del 2 de septiembre de 2026).
