from django import forms
from .models import ClassRoom


class ClassRoomForm(forms.ModelForm):

    class Meta:
        model = ClassRoom
        fields = ["name", "description"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full border rounded p-2"
            }),

            "description": forms.Textarea(attrs={
                "class": "w-full border rounded p-2",
                "rows": 4
            })
        }