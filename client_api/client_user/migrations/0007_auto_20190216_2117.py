# Generated by Django 2.1.5 on 2019-02-16 21:17

import client_user.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client_user', '0006_auto_20190216_1624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instrument',
            name='status',
            field=models.CharField(choices=[('ACTIVE', 'active'), ('INACTIVE', 'inactive'), ('DELETED', 'deleted')], default=client_user.models.InstrumentStatus('active'), max_length=30),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('ACTIVE', 'active'), ('COMPLETED', 'completed'), ('DELETED', 'deleted')], default=client_user.models.OrderStatus('active'), max_length=30),
        ),
        migrations.AlterField(
            model_name='order',
            name='type',
            field=models.CharField(choices=[('SELL', 'sell'), ('BUY', 'buy')], max_length=15),
        ),
    ]
