# Generated by Django 2.2.13 on 2020-08-30 06:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0002_auto_20200829_1601'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='finished_status',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(0, 'Done'), (1, 'Abandoned'), (2, 'Finished')], max_length=1, null=True, verbose_name='finished status'),
        ),
        migrations.AddField(
            model_name='activity',
            name='in_wishlist',
            field=models.BooleanField(blank=True, null=True, verbose_name='in wishlist'),
        ),
        migrations.AddField(
            model_name='activity',
            name='under_way',
            field=models.BooleanField(blank=True, null=True, verbose_name='under way'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='rating',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Detested'), (2, 'Hated'), (3, "Didn't like"), (4, "Didn't really like"), (5, 'Moderately enjoyed'), (6, 'Enjoyed'), (7, 'Liked'), (8, 'Liked a lot'), (9, 'Loved'), (10, 'Adored')], max_length=2, null=True, verbose_name='rating'),
        ),
    ]
