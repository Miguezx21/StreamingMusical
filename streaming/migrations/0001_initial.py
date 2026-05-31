from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TokenRecuperacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=100)),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('usado', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'TokenRecuperacion',
                'managed': True,
            },
        ),
    ]
