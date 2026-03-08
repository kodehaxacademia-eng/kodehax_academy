from django import forms
from .models import ClassRoom, TeacherProfile


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


class TeacherProfileForm(forms.ModelForm):

    class Meta:
        model = TeacherProfile
        fields = [
            "profile_picture",
            "full_name",
            "phone_number",
            "department",
            "qualification",
            "years_experience",
            "bio",
            "address",
            "website",
            "linkedin",
        ]

        widgets = {
            "profile_picture": forms.ClearableFileInput(attrs={
                "class": "hidden",
                "accept": "image/*",
            }),
            "full_name": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "Full name",
            }),
            "phone_number": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "Phone number",
            }),
            "department": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "Department / Subject",
            }),
            "qualification": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "Qualification",
            }),
            "years_experience": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "Years of experience",
                "min": 0,
            }),
            "bio": forms.Textarea(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "rows": 4,
                "placeholder": "Short bio",
            }),
            "address": forms.Textarea(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "rows": 3,
                "placeholder": "Address",
            }),
            "website": forms.URLInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "https://your-website.com",
            }),
            "linkedin": forms.URLInput(attrs={
                "class": "w-full rounded-xl border border-zinc-400 bg-white px-3 py-2.5 text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400",
                "placeholder": "https://linkedin.com/in/your-handle",
            }),
        }
