from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_parentlead_email_tutorlead_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='parentlead',
            name='teaching_mode_preference',
            field=models.CharField(
                choices=[
                    ('ONLINE', 'Online'),
                    ('HOME', 'Home visit'),
                    ('ACADEMY', 'Academy / coaching institute'),
                    ('ANY', 'Any of the above'),
                ],
                default='ANY',
                max_length=10,
            ),
        ),
    ]
