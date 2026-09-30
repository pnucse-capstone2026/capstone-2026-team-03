from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pronunciation", "0008_rename_special_difficulty_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="practicesentence",
            name="cached_ipa_variants",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='예: [{"label": "standard", "ipa": ["h", "a"]}]',
                verbose_name="허용 IPA 후보",
            ),
        ),
    ]
