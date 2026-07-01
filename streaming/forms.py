from django import forms


GENERO_CHOICES = [
    ('', '-- Selecciona --'),
    ('Masculino', 'Masculino'),
    ('Femenino', 'Femenino'),
    ('Otro', 'Otro'),
]


class RegistroForm(forms.Form):
    tipo_cuenta = forms.ChoiceField(
        choices=[('usuario', 'Usuario'), ('artista', 'Artista')],
        widget=forms.RadioSelect,
        label='Tipo de cuenta',
        initial='usuario',
    )
    nombre = forms.CharField(max_length=25, label='Nombre')
    apellido = forms.CharField(max_length=25, label='Apellido')
    email = forms.EmailField(max_length=100, label='Correo electrónico')
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=6,
        label='Contraseña',
    )
    confirmar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Confirmar contraseña',
    )
    genero = forms.ChoiceField(choices=GENERO_CHOICES, label='Género', required=False)
    pais_origen = forms.CharField(max_length=25, label='País de origen', required=False)
    fecha_nacimiento = forms.DateField(
        required=False,
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    # Solo para artistas
    nombre_artistico = forms.CharField(max_length=100, label='Nombre artístico', required=False)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirmar_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if cleaned_data.get('tipo_cuenta') == 'artista' and not cleaned_data.get('nombre_artistico'):
            self.add_error('nombre_artistico', 'El nombre artístico es requerido para artistas.')
        return cleaned_data


class RecuperarPasswordForm(forms.Form):
    email = forms.EmailField(max_length=100, label='Correo electrónico registrado')


class ResetPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=6,
        label='Nueva contraseña',
    )
    confirmar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Confirmar contraseña',
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirmar_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned_data


class AlbumForm(forms.Form):
    nombre_album = forms.CharField(max_length=100, label='Nombre del álbum')
    fecha_lanzamiento = forms.DateField(
        label='Fecha de lanzamiento',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )


class CancionForm(forms.Form):
    nombre_cancion = forms.CharField(max_length=100, label='Nombre de la canción')
    duracion = forms.CharField(
        max_length=8,
        label='Duración (HH:MM:SS)',
        widget=forms.TextInput(attrs={'placeholder': '00:03:30'}),
    )
    id_genero = forms.ChoiceField(label='Género')
    id_album = forms.ChoiceField(label='Álbum')

    def __init__(self, *args, generos=None, albums=None, **kwargs):
        super().__init__(*args, **kwargs)
        if generos:
            self.fields['id_genero'].choices = [(g.idgenero, g.nombregenero) for g in generos]
        if albums:
            self.fields['id_album'].choices = [(a.idalbum, a.nombrealbum) for a in albums]


class PlaylistForm(forms.Form):
    nombre_playlist = forms.CharField(max_length=100, label='Nombre de la playlist')
    descripcion = forms.CharField(
        max_length=255, label='Descripción', required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
