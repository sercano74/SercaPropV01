from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('a00seg', '0001_initial'),
        ('a03Prop', '0005_solicitudvisita_motivo_rechazo'),
    ]

    operations = [
        # Intención de arriendo
        migrations.AddField(
            model_name='solicitudvisita',
            name='intencion_arriendo',
            field=models.BooleanField(default=False, verbose_name='Intención de arriendo manifestada'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='intencion_arriendo_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Intención manifestada el'),
        ),
        # Contrato de arriendo (PDF subido por corredor)
        migrations.AddField(
            model_name='solicitudvisita',
            name='contrato_arriendo',
            field=models.FileField(blank=True, null=True, upload_to='contratos_arriendo/', verbose_name='Contrato de arriendo (PDF)'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='contrato_arriendo_subido_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contratos_arriendo_subidos', to='a00seg.User', verbose_name='Contrato subido por'),
        ),
        # Datos de notaría
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_nombre',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nombre de la notaría'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_direccion',
            field=models.CharField(blank=True, max_length=255, verbose_name='Dirección de la notaría'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_fecha',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha notaría'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_hora',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora notaría'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_confirmada',
            field=models.BooleanField(default=False, verbose_name='Cita notarial confirmada por el usuario'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='notaria_confirmada_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Cita notarial confirmada el'),
        ),
        # Cierre del caso
        migrations.AddField(
            model_name='solicitudvisita',
            name='caso_cerrado',
            field=models.BooleanField(default=False, verbose_name='Caso cerrado'),
        ),
        migrations.AddField(
            model_name='solicitudvisita',
            name='caso_cerrado_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Caso cerrado el'),
        ),
    ]
