import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_alter_productvariant_discount_percentage'),
        ('store', '0003_alter_cartitem_custom_image'),
    ]

    operations = [
        # 1. Clear unique_together that references product first
        migrations.AlterUniqueTogether(
            name='wishlistitem',
            unique_together=set(),
        ),
        # 2. Remove old product field
        migrations.RemoveField(
            model_name='wishlistitem',
            name='product',
        ),
        # 3. Add new variant field
        migrations.AddField(
            model_name='wishlistitem',
            name='variant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='wishlist_items',
                to='products.productvariant',
            ),
        ),
        # 4. Set new unique_together with variant
        migrations.AlterUniqueTogether(
            name='wishlistitem',
            unique_together={('wishlist', 'variant')},
        ),
    ]