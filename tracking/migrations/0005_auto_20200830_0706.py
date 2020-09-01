# Generated by Django 2.2.13 on 2020-08-30 07:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0004_auto_20200830_0700'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='activity',
            name='finished_status',
        ),
        migrations.RemoveField(
            model_name='activity',
            name='in_wishlist',
        ),
        migrations.RemoveField(
            model_name='activity',
            name='under_way',
        ),
        migrations.AddField(
            model_name='activity',
            name='status',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(0, 'In wishlist'), (1, 'Under way'), (2, 'Done'), (3, 'Abandoned'), (4, 'Finished')], null=True, verbose_name='status'),
        ),
    ]