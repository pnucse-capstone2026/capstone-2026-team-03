from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pronunciation", "0007_rename_advanced_difficulty_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="practicesentence",
            name="difficulty",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "초급"),
                    (2, "중급"),
                    (3, "상급"),
                    (4, "심화"),
                ],
                default=1,
                verbose_name="난이도",
            ),
        ),
    ]
