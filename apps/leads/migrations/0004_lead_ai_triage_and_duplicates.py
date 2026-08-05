import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0003_parentlead_teaching_mode_preference'),
    ]

    operations = [
        migrations.AddField(
            model_name='parentlead',
            name='ai_priority',
            field=models.CharField(
                choices=[
                    ('UNSCORED', 'Not yet triaged'),
                    ('HIGH', 'High priority'),
                    ('MEDIUM', 'Medium priority'),
                    ('LOW', 'Low priority'),
                ],
                default='UNSCORED',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='parentlead',
            name='ai_triage_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='parentlead',
            name='is_potential_duplicate',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parentlead',
            name='duplicate_of',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='duplicates', to='leads.parentlead',
            ),
        ),
        migrations.AddField(
            model_name='tutorlead',
            name='ai_priority',
            field=models.CharField(
                choices=[
                    ('UNSCORED', 'Not yet triaged'),
                    ('HIGH', 'High priority'),
                    ('MEDIUM', 'Medium priority'),
                    ('LOW', 'Low priority'),
                ],
                default='UNSCORED',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='tutorlead',
            name='ai_triage_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='tutorlead',
            name='is_potential_duplicate',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tutorlead',
            name='duplicate_of',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='duplicates', to='leads.tutorlead',
            ),
        ),
    ]
