from django.db import migrations

OLD_TO_NEW = {
    "slim": "full_cover",
    "top": "top_cover",
    "bottom": "bottom_cover",
    "palm": "palm_rest",
    "full": "full_body_wrap",
}

def fix_laptop_case_types(apps, schema_editor):
    ProductVariant = apps.get_model("products", "ProductVariant")
    for old_value, new_value in OLD_TO_NEW.items():
        updated = ProductVariant.objects.filter(
            case_type=old_value,
            device_model__device_type="laptop",
        ).update(case_type=new_value)
        print(f"Updated {updated} variant(s): '{old_value}' -> '{new_value}'")

def reverse_fix(apps, schema_editor):
    pass  # no safe reverse — old values overlap with phone case types

class Migration(migrations.Migration):

    dependencies = [
        ("products", "0016_alter_productvariant_case_type"),
    ]

    operations = [
        migrations.RunPython(fix_laptop_case_types, reverse_fix),
    ]
