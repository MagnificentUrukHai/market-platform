# Generated by Django 2.1.5 on 2019-02-17 13:53

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ClientUser',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('password',
                 models.CharField(max_length=128, verbose_name='password')),
                ('created_at_dt', models.DateTimeField(auto_now_add=True)),
                ('updated_at_dt', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(max_length=40, unique=True)),
                ('first_name', models.CharField(blank=True, max_length=30)),
                ('last_name', models.CharField(blank=True, max_length=30)),
                ('status',
                 models.CharField(choices=[('VERIFIED', 'verified'),
                                           ('UNVERIFIED', 'unverified')],
                                  default='unverified',
                                  max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('password_changed_at_dt',
                 models.DateTimeField(default=django.utils.timezone.now)),
                ('totp_token', models.CharField(blank=True, max_length=30)),
                ('is_email_verified', models.BooleanField(default=False)),
                ('email_verified_at_dt',
                 models.DateTimeField(blank=True, null=True)),
                ('email_verification_code',
                 models.UUIDField(default=uuid.uuid4)),
                ('is_only_view_allowed', models.BooleanField(default=False)),
                ('comment',
                 models.CharField(blank=True, default='', max_length=500)),
                ('language',
                 models.CharField(blank=True, default='en', max_length=5)),
                ('country', models.CharField(blank=True, max_length=255)),
                ('phone',
                 models.CharField(blank=True, default='', max_length=20)),
                ('is_superuser', models.BooleanField(default=False)),
                ('last_login', models.DateTimeField(blank=True, null=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ClientUserIp',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('is_approved', models.BooleanField(default=True)),
                ('created_at_dt', models.DateTimeField(auto_now_add=True)),
                ('updated_at_dt', models.DateTimeField(auto_now=True)),
                ('user',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                   related_name='user_ips',
                                   to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('title', models.CharField(max_length=30, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='FiatBalance',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('amount',
                 models.DecimalField(decimal_places=8,
                                     default=0,
                                     max_digits=20)),
                ('currency',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to='client_user.Currency')),
                ('user',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Instrument',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('status',
                 models.CharField(choices=[('ACTIVE', 'active'),
                                           ('INACTIVE', 'inactive'),
                                           ('DELETED', 'deleted')],
                                  default='active',
                                  max_length=30)),
                ('credit_created_at_d', models.DateField(null=True)),
                ('credit_expires_at_d', models.DateField(null=True)),
                ('credit_interest_percentage',
                 models.DecimalField(decimal_places=3, max_digits=5,
                                     null=True)),
                ('created_at_dt', models.DateTimeField(auto_now_add=True)),
                ('updated_at_dt', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='InstrumentBalance',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('amount',
                 models.DecimalField(decimal_places=8,
                                     default=0,
                                     max_digits=20)),
                ('instrument',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to='client_user.Instrument')),
                ('user',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id',
                 models.AutoField(auto_created=True,
                                  primary_key=True,
                                  serialize=False,
                                  verbose_name='ID')),
                ('type',
                 models.CharField(choices=[('SELL', 'sell'), ('BUY', 'buy')],
                                  max_length=15)),
                ('status',
                 models.CharField(choices=[('ACTIVE', 'active'),
                                           ('COMPLETED', 'completed'),
                                           ('DELETED', 'deleted')],
                                  default='active',
                                  max_length=30)),
                ('price', models.DecimalField(decimal_places=8,
                                              max_digits=20)),
                ('total_sum',
                 models.DecimalField(decimal_places=8,
                                     default=0,
                                     max_digits=20)),
                ('remaining_sum',
                 models.DecimalField(decimal_places=8,
                                     default=0,
                                     max_digits=20)),
                ('created_at_dt', models.DateTimeField(auto_now_add=True)),
                ('updated_at_dt', models.DateTimeField(auto_now=True)),
                ('expires_in', models.PositiveIntegerField()),
                ('instrument',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   related_name='instrument',
                                   to='client_user.Instrument')),
                ('user',
                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                   to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
