import csv
import io
import json

from django import forms

from .models import QuestionTemplate


def parse_parameter_lines(raw_text):
    params = {}
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, values = line.split(":", 1)
        cleaned_key = key.strip()
        cleaned_values = [item.strip() for item in values.split(",") if item.strip()]
        if cleaned_key and cleaned_values:
            params[cleaned_key] = cleaned_values
    return params


class QuestionTemplateForm(forms.ModelForm):
    parameter_lines = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 4,
            "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            "placeholder": "k: 2,3,4,5\nx: 5,10,15",
        }),
        help_text="One parameter per line using name: value1,value2.",
    )
    test_cases_json = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5,
            "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            "placeholder": '[{"input": [[1,2,3]], "expected": 6}]',
        }),
        help_text="JSON list of test cases. Strings may include placeholders like {k}.",
    )

    class Meta:
        model = QuestionTemplate
        fields = [
            "title_template",
            "description_template",
            "difficulty",
            "topic",
            "starter_code_template",
            "function_name",
            "hint1_template",
            "hint2_template",
            "parameter_lines",
            "test_cases_json",
        ]
        widgets = {
            "title_template": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "description_template": forms.Textarea(attrs={
                "rows": 5,
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "difficulty": forms.Select(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "topic": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
                "placeholder": "arrays, strings, recursion, sorting",
            }),
            "starter_code_template": forms.Textarea(attrs={
                "rows": 5,
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "function_name": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "hint1_template": forms.Textarea(attrs={
                "rows": 2,
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
            "hint2_template": forms.Textarea(attrs={
                "rows": 2,
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/40 px-3 py-2.5 text-slate-100",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["parameter_lines"].initial = "\n".join(
                f"{key}: {','.join(values)}"
                for key, values in (self.instance.parameter_schema or {}).items()
            )
            self.fields["test_cases_json"].initial = json.dumps(
                self.instance.test_cases_template or [],
                indent=2,
            )

    def clean_test_cases_json(self):
        raw_value = self.cleaned_data["test_cases_json"]
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError("Test cases JSON must be a list.")
        return parsed

    def clean_parameter_lines(self):
        return parse_parameter_lines(self.cleaned_data.get("parameter_lines", ""))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.parameter_schema = self.cleaned_data["parameter_lines"]
        instance.test_cases_template = self.cleaned_data["test_cases_json"]
        if commit:
            instance.save()
        return instance


class QuestionTemplateCSVImportForm(forms.Form):
    csv_file = forms.FileField()

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        return csv_file

    def parse_rows(self):
        csv_file = self.cleaned_data["csv_file"]
        text = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
