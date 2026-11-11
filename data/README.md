# Datos

Esta carpeta no guarda datos en Git (ver `.gitignore`). Los datos son los procesos de contratación de SECOP II del portal de datos abiertos datos.gov.co ([dataset SECOP II](https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II/a8sx-pfr3/about_data)), descargados el **2 de septiembre de 2026**. Vienen en un `.zip` de unos 1,7 GB que, descomprimido, pesa varios GB. Spark no lee archivos `.zip`, así que hay que descomprimirlo antes de cargarlo.

1. Descarga el `.zip` desde [Google Drive](https://drive.google.com/file/d/1S-0hBc4gr9rwaRi_cEMqCO7G80qV-fHv/view?usp=drive_link) (no está en el repositorio por su tamaño) y descomprímelo.
2. Abre la consola de MinIO (http://localhost:9002), entra al bucket `rawdata` y sube el CSV dentro de la carpeta `secop/`. La ruta final debe quedar como `s3a://rawdata/secop/<archivo>.csv`. Si el `.zip` trae varios CSV, súbelos todos a esa carpeta.

Si el enlace de Drive no está disponible para quien lo necesite, el dataset original se puede volver a descargar desde datos.gov.co (el contenido cambia con el tiempo, así que no será idéntico al del 2 de septiembre de 2026).
