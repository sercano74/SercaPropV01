"""Almacenamiento de archivos de Serca Propiedades en Cloudinary.

Por qué existe este módulo
--------------------------
``cloudinary_storage.storage.MediaCloudinaryStorage`` fija
``RESOURCE_TYPE = 'image'``, por lo que sube **todos** los archivos con
``resource_type='image'``. Cloudinary solo acepta imágenes y PDF por ese
pipeline: cuando se sube un Word (``.docx`` es un ZIP) responde
``BadRequest: Unsupported ZIP file``; la excepción no se controla y el usuario
recibe la página 500 ("Algo salió mal"). Esto explica por qué el PDF se subía
sin problema y el Word fallaba.

``SercaMediaStorage`` elige el ``resource_type`` según la extensión:

* imágenes → ``image`` (permite transformaciones y miniaturas),
* videos → ``video``,
* PDF → ``image`` (Cloudinary los sirve por el pipeline de imágenes y los
  archivos ya subidos se guardaron así: sus URLs no deben cambiar),
* cualquier otro documento (Word, Excel, PowerPoint, texto, ZIP, etc.) →
  ``raw``, que acepta cualquier formato.

Los ``public_id`` antiguos (guardados sin extensión) se subieron como
``image``, así que se siguen resolviendo igual para no romper los enlaces
existentes.
"""
import os

from cloudinary_storage.storage import RESOURCE_TYPES, MediaCloudinaryStorage

EXTENSIONES_IMAGEN = frozenset({
    "jpg", "jpeg", "jpe", "jfif", "jp2", "j2k", "jpc", "jxr", "hdp", "wdp",
    "png", "gif", "webp", "avif", "bmp", "tif", "tiff", "ico", "heic", "heif",
    "svg", "psd", "eps",
})

EXTENSIONES_VIDEO = frozenset({
    "mp4", "m4v", "mov", "webm", "avi", "mkv", "wmv", "flv", "mpeg", "mpg",
    "ogv", "3gp", "3g2", "mts", "m2ts",
})

# Cloudinary sirve los PDF con el pipeline de imágenes, no con 'raw'.
EXTENSIONES_IMAGEN_Y_PDF = EXTENSIONES_IMAGEN | {"pdf"}


class SercaMediaStorage(MediaCloudinaryStorage):
    """Storage de medios que envía cada archivo al pipeline correcto de Cloudinary."""

    def _get_resource_type(self, name):
        """Devuelve 'image', 'video' o 'raw' según la extensión del archivo."""
        extension = self._get_extension(name)
        if extension is None:
            # public_id antiguo, sin extensión: se guardó como 'image'.
            return RESOURCE_TYPES["IMAGE"]
        if extension in EXTENSIONES_IMAGEN_Y_PDF:
            return RESOURCE_TYPES["IMAGE"]
        if extension in EXTENSIONES_VIDEO:
            return RESOURCE_TYPES["VIDEO"]
        return RESOURCE_TYPES["RAW"]

    def get_available_name(self, name, max_length=None):
        """Recorta los nombres demasiado largos sin perder la extensión.

        ``FileField`` limita el nombre a ``max_length`` (100 por defecto). El
        recorte original (``name[:max_length]``) podía cortar el ``.docx``,
        dejando el archivo sin extensión y volviendo a subirlo como imagen.
        Aquí se conserva la extensión para que el archivo siga siendo
        reconocible.
        """
        if max_length is None or len(name) <= max_length:
            return name

        carpeta, nombre_archivo = os.path.split(name)
        raiz, extension = os.path.splitext(nombre_archivo)
        largo_disponible = max(max_length - len(carpeta) - len(extension) - 1, 1)
        nombre_recortado = f"{raiz[:largo_disponible]}{extension}"
        return os.path.join(carpeta, nombre_recortado) if carpeta else nombre_recortado

    @staticmethod
    def _get_extension(name):
        """Extensión en minúsculas y sin punto, o ``None`` si el nombre no tiene."""
        _, extension = os.path.splitext(os.path.basename(name or ""))
        return extension.lower().lstrip(".") or None
