from django import forms
from .models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        # These are the fields admin can fill in
        fields = ['name', 'description', 'image', 'is_active']

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Category name is required.')
        # Check if another category already has this name
        # exclude(pk=self.instance.pk) means ignore current category when editing
        if Category.objects.filter(
            name__iexact=name
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError('A category with this name already exists.')
        return name