from django import forms
from .models import Task
from django.core.exceptions import ValidationError
import json

class TaskForm(forms.ModelForm):
    """Enhanced task form with better widgets and validation."""
    
    class Meta:
        model = Task
        fields = ['title', 'due_date', 'estimated_hours', 'importance', 'dependencies']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter task title...'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.5',
                'step': '0.5',
                'min': '0.1'
            }),
            'importance': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'dependencies': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'e.g., 1,3,5 (comma-separated task IDs)'
            })
        }
        labels = {
            'title': '📝 Task Title',
            'due_date': '📅 Due Date',
            'estimated_hours': '⏱️ Estimated Hours',
            'importance': '⭐ Importance (1-10)',
            'dependencies': '🔗 Dependencies'
        }
        help_texts = {
            'title': 'Clear, actionable task description',
            'due_date': 'When does this need to be completed?',
            'estimated_hours': 'How long will this take? (0.5 = 30 minutes)',
            'importance': 'How critical is this task?',
            'dependencies': 'Task IDs this depends on (optional)'
        }
    
    def clean_estimated_hours(self):
        """Validate estimated hours."""
        hours = self.cleaned_data.get('estimated_hours')
        if hours <= 0:
            raise ValidationError('Estimated hours must be greater than 0')
        if hours > 1000:
            raise ValidationError('Estimated hours seems unrealistic (max: 1000)')
        return hours
    
    def clean_dependencies(self):
        """Validate dependencies format."""
        deps = self.cleaned_data.get('dependencies', '')
        if not deps:
            return ''
        
        try:
            dep_ids = [int(d.strip()) for d in deps.split(',') if d.strip()]
            
            # Check if tasks exist
            from .models import Task
            for dep_id in dep_ids:
                if not Task.objects.filter(id=dep_id).exists():
                    raise ValidationError(f'Task with ID {dep_id} does not exist')
            
            return ','.join(map(str, dep_ids))
        except ValueError:
            raise ValidationError('Dependencies must be comma-separated numbers (e.g., 1,3,5)')


class JSONImportForm(forms.Form):
    """Form for bulk importing tasks from JSON."""
    
    json_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm',
            'placeholder': '[\n  {\n    "title": "Task 1",\n    "due_date": "2025-12-01",\n    "estimated_hours": 2,\n    "importance": 8,\n    "dependencies": ""\n  }\n]',
            'rows': 10
        }),
        label='📋 Paste JSON Array',
        help_text='Paste an array of task objects. Each task must have: title, due_date, estimated_hours, importance'
    )
    
    def clean_json_data(self):
        """Validate JSON format and structure."""
        data = self.cleaned_data.get('json_data')
        
        try:
            tasks = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValidationError(f'Invalid JSON: {str(e)}')
        
        if not isinstance(tasks, list):
            raise ValidationError('JSON must be an array of tasks')
        
        if len(tasks) == 0:
            raise ValidationError('JSON array is empty')
        
        if len(tasks) > 100:
            raise ValidationError('Maximum 100 tasks can be imported at once')
        
        # Validate each task
        required_fields = ['title', 'due_date', 'estimated_hours', 'importance']
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValidationError(f'Task {i+1} is not a valid object')
            
            missing_fields = [f for f in required_fields if f not in task]
            if missing_fields:
                raise ValidationError(
                    f'Task {i+1} missing required fields: {", ".join(missing_fields)}'
                )
            
            # Validate field types and ranges
            if not isinstance(task['title'], str) or not task['title'].strip():
                raise ValidationError(f'Task {i+1}: title must be a non-empty string')
            
            try:
                from datetime import datetime
                datetime.strptime(task['due_date'], '%Y-%m-%d')
            except (ValueError, TypeError):
                raise ValidationError(
                    f'Task {i+1}: due_date must be in YYYY-MM-DD format'
                )
            
            try:
                hours = float(task['estimated_hours'])
                if hours <= 0 or hours > 1000:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError(
                    f'Task {i+1}: estimated_hours must be a number between 0 and 1000'
                )
            
            try:
                importance = int(task['importance'])
                if importance < 1 or importance > 10:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError(
                    f'Task {i+1}: importance must be an integer between 1 and 10'
                )
        
        return data


class TaskFilterForm(forms.Form):
    """Form for filtering tasks."""
    
    PRIORITY_CHOICES = [
        ('all', 'All Tasks'),
        ('high', 'High Priority (80+)'),
        ('medium', 'Medium Priority (50-80)'),
        ('low', 'Low Priority (<50)')
    ]
    
    STATUS_CHOICES = [
        ('all', 'All'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue')
    ]
    
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
            'placeholder': '🔍 Search tasks...'
        })
    )