from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='ai_moderation_status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Awaiting AI check'),
                    ('OK', 'AI found nothing concerning'),
                    ('FLAGGED', 'AI flagged for staff attention'),
                    ('SKIPPED', 'AI moderation unavailable when submitted'),
                ],
                default='PENDING',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='review',
            name='ai_moderation_notes',
            field=models.TextField(
                blank=True,
                help_text='Short AI-written reason, only meaningful when ai_moderation_status is FLAGGED.',
            ),
        ),
    ]
