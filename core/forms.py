from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Extras, Producto, CategoriaProducto, GrupoOpcion


class ExtraForm(forms.ModelForm):
    class Meta:
        model = Extras
        fields = ['nombre', 'precio']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Cheddar extra, Bacon crocante...',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre del extra es obligatorio.')
        return nombre

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is None:
            raise ValidationError('El precio es obligatorio.')
        if precio < Decimal('0.00'):
            raise ValidationError('El precio no puede ser negativo.')
        return precio


class ProductoForm(forms.ModelForm):
    grupos = forms.ModelMultipleChoiceField(
        queryset=GrupoOpcion.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'grupo-checkbox'})
    )
    extras = forms.ModelMultipleChoiceField(
        queryset=Extras.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'extra-checkbox'})
    )

    class Meta:
        model = Producto
        fields = ['nombre', 'precio', 'idcategoria', 'descripcion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Hamburguesa Doble Cheddar...',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
            'idcategoria': forms.Select(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del producto, ingredientes principales...',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
            'imagen': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'style': 'width: 100%; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 4px; box-sizing: border-box;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Precargar grupos y extras asociados al producto
            self.fields['grupos'].initial = self.instance.productogrupoopcion_set.values_list('idgrupo_id', flat=True)
            self.fields['extras'].initial = self.instance.productoextras_set.values_list('idextra_id', flat=True)

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        if not nombre:
            raise ValidationError('El nombre del producto es obligatorio.')
        return nombre

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is None:
            raise ValidationError('El precio es obligatorio.')
        if precio < Decimal('0.00'):
            raise ValidationError('El precio no puede ser negativo.')
        return precio
