from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("metrics", "0013_suitehistory"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="History",
            new_name="TestHistory",
        ),
    ]
