"""Validación de archivos subidos por los usuarios.

Centraliza qué formatos y qué tamaño se aceptan, para que cualquier vista que
reciba un archivo entregue un mensaje claro en vez de fallar con un error 500.
"""
import os

# Formatos aceptados para documentos de gestión (OG, documentos legales,
# órdenes, promesas, contratos, etc.).
EXTENSIONES_DOCUMENTO = frozenset({
    # Documentos
    "pdf", "doc", "docx", "dot", "dotx", "odt", "rtf", "txt", "pages",
    # Planillas de cálculo
    "xls", "xlsx", "xlsm", "ods", "csv", "numbers",
    # Presentaciones
    "ppt", "pptx", "odp", "key",
    # Imágenes (fotografías de documentos, capturas, escaneos)
    "jpg", "jpeg", "jpe", "png", "webp", "gif", "bmp", "tif", "tiff",
    "heic", "heif", "avif",
    # Carpetas comprimidas con antecedentes
    "zip", "rar", "7z",
})

FORMATOS_ACEPTADOS_TEXTO = (
    "PDF, Word (.doc/.docx), Excel (.xls/.xlsx), PowerPoint (.ppt/.pptx), "
    "OpenDocument (.odt/.ods/.odp), RTF, TXT, CSV, imágenes "
    "(JPG, PNG, WEBP, GIF, TIFF, HEIC) y ZIP"
)

# Cloudinary limita los archivos grandes según el plan contratado y Django
# transmite a disco lo que supera FILE_UPLOAD_MAX_MEMORY_SIZE; 10 MB cubre con
# holgura una Orden de Gestión escaneada.
TAMANO_MAXIMO_MB = 10


def extension_de_archivo(archivo):
    """Extensión del archivo en minúsculas y sin punto (cadena vacía si no tiene)."""
    nombre = getattr(archivo, "name", "") or ""
    _, extension = os.path.splitext(os.path.basename(nombre))
    return extension.lower().lstrip(".")


def tamano_en_mb(archivo):
    """Tamaño del archivo en MB (0 si el archivo no lo informa)."""
    return (getattr(archivo, "size", 0) or 0) / (1024 * 1024)


def validar_archivo_documento(
    archivo,
    *,
    etiqueta="El archivo",
    extensiones=EXTENSIONES_DOCUMENTO,
    max_mb=TAMANO_MAXIMO_MB,
):
    """Valida un archivo subido.

    Devuelve ``None`` si el archivo se puede guardar o un mensaje de error en
    español, listo para mostrarle al usuario con ``messages.error``.
    """
    if not archivo:
        return f"{etiqueta} no fue recibido. Vuelve a intentarlo."

    nombre = getattr(archivo, "name", "") or "sin nombre"
    extension = extension_de_archivo(archivo)

    if not extension:
        return (
            f"{etiqueta} '{nombre}' no tiene extensión, por lo que no se puede "
            f"verificar su formato. Formatos aceptados: {FORMATOS_ACEPTADOS_TEXTO}."
        )

    if extension not in extensiones:
        return (
            f"{etiqueta} '{nombre}' no es un formato permitido "
            f"(formato .{extension}). Formatos aceptados: {FORMATOS_ACEPTADOS_TEXTO}."
        )

    if max_mb and tamano_en_mb(archivo) > max_mb:
        return (
            f"{etiqueta} '{nombre}' pesa {tamano_en_mb(archivo):.1f} MB y el máximo "
            f"permitido es {max_mb} MB."
        )

    return None
