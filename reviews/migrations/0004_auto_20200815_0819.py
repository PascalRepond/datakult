# Generated by Django 2.2.13 on 2020-08-15 08:19

from django.db import migrations
import djrichtextfield.models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0003_auto_20200815_0818'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='comment',
            field=djrichtextfield.models.RichTextField(blank=True, max_length=3000, null=True, verbose_name='comment'),
        ),
    ]
