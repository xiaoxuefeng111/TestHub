from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app_automation', '0002_initial'),
        ('ui_automation', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiexecutionrecord',
            name='app_device',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='app_automation.appdevice', verbose_name='目标设备'),
        ),
        migrations.AddField(
            model_name='aiexecutionrecord',
            name='app_package',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='app_automation.apppackage', verbose_name='目标应用包'),
        ),
        migrations.AlterField(
            model_name='aiexecutionrecord',
            name='execution_mode',
            field=models.CharField(choices=[('text', '文本模式'), ('mobile', '移动端自主模式')], default='text', max_length=20, verbose_name='执行模式'),
        ),
    ]
