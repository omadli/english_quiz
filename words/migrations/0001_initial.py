# Generated by Django 4.2.1 on 2023-05-18 06:20

import django.core.validators
from django.db import migrations, models
import words.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Word',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('book', models.PositiveSmallIntegerField(help_text='Kitob raqami', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(6)])),
                ('unit', models.PositiveSmallIntegerField(help_text='Unit raqami', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)])),
                ('en', models.CharField(db_column='en', help_text='Inglizchasi', max_length=100, verbose_name='english')),
                ('uz', models.CharField(db_column='uz', help_text="O'zbekcha tarjimasi", max_length=100, verbose_name='uzbek')),
                ('definition', models.TextField(blank=True, help_text="Ta'rifi", null=True)),
                ('example', models.TextField(blank=True, help_text='Namuna', null=True)),
                ('pronunciation', models.CharField(blank=True, help_text='Talaffuzi', max_length=100, null=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to=words.models.upload_word_image)),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.AddConstraint(
            model_name='word',
            constraint=models.UniqueConstraint(fields=('book', 'en'), name='book and word'),
        ),
    ]
