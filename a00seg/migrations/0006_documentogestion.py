# Generated manually - DocumentoGestion para la biblioteca documental de gestión

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('a00seg', '0005_comuna_descripcion_seo'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentoGestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categoria', models.CharField(choices=[('ventas', 'Ventas'), ('arriendos', 'Arriendos'), ('srt', 'SRT (Arriendos vacacionales)'), ('servicios', 'Servicios Profesionales')], max_length=20, verbose_name='Categoría / Producto')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre del documento')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción', help_text='Descripción mejorada: para qué sirve, cómo usarlo, en qué etapa se sube, etc.')),
                ('archivo', models.FileField(upload_to='docs_gestion/', verbose_name='Archivo', help_text='PDF, Word, Excel, imágenes u otros formatos')),
                ('tipo_documento', models.CharField(choices=[('plantilla', 'Plantilla (para rellenar)'), ('referencia', 'Documento de referencia / instructivo')], default='referencia', max_length=20, verbose_name='Tipo de documento')),
                ('version', models.CharField(blank=True, max_length=20, verbose_name='Versión', help_text='Ej: v1.0, v2.3')),
                ('tags', models.CharField(blank=True, max_length=255, verbose_name='Etiquetas / palabras clave', help_text='Separadas por coma. Ej: orden de gestion, og, plantilla')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo', help_text='Los documentos inactivos no se muestran a los corredores')),
                ('descargas', models.PositiveIntegerField(default=0, verbose_name='N° de descargas')),
                ('subido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_gestion_subidos', to='a00seg.user', verbose_name='Subido por')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
            ],
            options={
                'verbose_name': 'Documento de gestión',
                'verbose_name_plural': 'Documentos de gestión',
                'ordering': ['categoria', 'nombre'],
            },
        ),
    ]
