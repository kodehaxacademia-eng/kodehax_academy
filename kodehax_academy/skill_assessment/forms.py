from django import forms


class SelfAssessmentForm(forms.Form):
    LANGUAGE_CHOICES = (
        ("beginner", "Beginner familiarity"),
        ("intermediate", "Intermediate familiarity"),
        ("advanced", "Advanced familiarity"),
    )
    EXPERIENCE_CHOICES = (
        ("new", "Just getting started"),
        ("less_than_6m", "Less than 6 months"),
        ("6_to_12m", "6 to 12 months"),
        ("1_to_2y", "1 to 2 years"),
        ("2y_plus", "More than 2 years"),
    )
    PLATFORM_CHOICES = (
        ("leetcode", "LeetCode"),
        ("hackerrank", "HackerRank"),
        ("codechef", "CodeChef"),
        ("codeforces", "Codeforces"),
        ("github", "GitHub"),
        ("other", "Other"),
    )
    CONFIDENCE_CHOICES = (
        ("1", "1 - Very low"),
        ("2", "2 - Low"),
        ("3", "3 - Moderate"),
        ("4", "4 - Strong"),
        ("5", "5 - Very strong"),
    )

    programming_language_familiarity = forms.ChoiceField(choices=LANGUAGE_CHOICES)
    coding_experience_duration = forms.ChoiceField(choices=EXPERIENCE_CHOICES)
    platforms_used = forms.MultipleChoiceField(
        choices=PLATFORM_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    confidence_rating = forms.ChoiceField(
        choices=CONFIDENCE_CHOICES,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programming_language_familiarity"].widget.attrs.update(
            {"class": "form-select"}
        )
        self.fields["coding_experience_duration"].widget.attrs.update(
            {"class": "form-select"}
        )


class MCQAssessmentForm(forms.Form):
    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        questions = questions or []
        for question in questions:
            option_choices = [
                (option["value"], option["label"])
                for option in question.options
            ]
            self.fields[f"question_{question.id}"] = forms.ChoiceField(
                choices=option_choices,
                widget=forms.RadioSelect,
                label=question.question_text,
            )


class CodingAssessmentForm(forms.Form):
    def __init__(self, *args, problems=None, **kwargs):
        super().__init__(*args, **kwargs)
        problems = problems or []
        for problem in problems:
            self.fields[f"problem_{problem.id}"] = forms.CharField(
                label=problem.title,
                widget=forms.Textarea(
                    attrs={
                        "rows": 14,
                        "spellcheck": "false",
                        "class": "code-editor-input",
                    }
                ),
            )
