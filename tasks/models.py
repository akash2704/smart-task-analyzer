from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Task(models.Model):
    """
    Enhanced Task model with comprehensive validation and helper methods.
    """
    title = models.CharField(max_length=200)
    due_date = models.DateField()
    estimated_hours = models.FloatField(
        help_text="Estimated hours to complete (must be > 0)"
    )
    importance = models.IntegerField(
        choices=[(i, i) for i in range(1, 11)],
        help_text="Priority rating from 1 (low) to 10 (high)"
    )
    dependencies = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Comma-separated task IDs this task depends on (e.g., '1,3,5')"
    )
    
    # Metadata fields
    created_at = models.DateTimeField(default=timezone.now)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # User feedback for ML adaptation
    was_helpful = models.BooleanField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['due_date', 'completed']),
            models.Index(fields=['importance']),
        ]
    
    def clean(self):
        """Validate task data before saving."""
        errors = {}
        
        # Validate estimated hours
        if self.estimated_hours <= 0:
            errors['estimated_hours'] = "Estimated hours must be greater than 0"
        
        if self.estimated_hours > 1000:
            errors['estimated_hours'] = "Estimated hours seems unrealistic (max: 1000)"
        
        # Validate importance
        if self.importance < 1 or self.importance > 10:
            errors['importance'] = "Importance must be between 1 and 10"
        
        # Validate due date
        if self.due_date and self.due_date < timezone.now().date():
            # Warning but not error - allow overdue tasks
            pass
        
        # Validate dependencies format
        if self.dependencies:
            try:
                dep_ids = [int(d.strip()) for d in self.dependencies.split(',') if d.strip()]
                # Check for self-reference
                if self.pk and self.pk in dep_ids:
                    errors['dependencies'] = "Task cannot depend on itself"
            except ValueError:
                errors['dependencies'] = "Dependencies must be comma-separated numbers"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_dependency_ids(self):
        """Return list of dependency task IDs."""
        if not self.dependencies:
            return []
        try:
            return [int(d.strip()) for d in self.dependencies.split(',') if d.strip()]
        except ValueError:
            return []
    
    def is_overdue(self):
        """Check if task is past due date."""
        return self.due_date < timezone.now().date() and not self.completed
    
    def days_until_due(self):
        """Calculate days until due (negative if overdue)."""
        delta = self.due_date - timezone.now().date()
        return delta.days
    
    def __str__(self):
        status = "✓" if self.completed else "○"
        return f"{status} {self.title}"