from django.db import models

class Task(models.Model):
    title = models.CharField(max_length=200)
    due_date = models.DateField()
    estimated_hours = models.FloatField()
    importance = models.IntegerField(choices=[(i, i) for i in range(1, 11)])
    # Storing dependencies as text IDs (comma separated) for speed in this exam
    # In real life, use ManyToMany. For exam speed: "1,4,5"
    dependencies = models.CharField(max_length=200, blank=True, help_text="IDs of tasks this depends on")

    def __str__(self):
        return self.title