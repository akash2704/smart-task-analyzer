from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from .models import Task
from .forms import TaskForm, JSONImportForm
from .services import TaskPrioritizer, AdaptivePrioritizer
import json
from datetime import datetime


def index(request):
    """
    Main view with task list and sorting strategies.
    """
    # Get current strategy from query params
    current_strategy = request.GET.get('strategy', 'balanced')
    show_completed = request.GET.get('show_completed', 'false') == 'true'
    
    # Handle form submissions
    if request.method == 'POST':
        if 'add_task' in request.POST:
            form = TaskForm(request.POST)
            if form.is_valid():
                try:
                    form.save()
                    return redirect(f'/?strategy={current_strategy}')
                except ValidationError as e:
                    # Re-render with errors
                    pass
        
        elif 'import_json' in request.POST:
            json_form = JSONImportForm(request.POST)
            if json_form.is_valid():
                try:
                    tasks_data = json.loads(json_form.cleaned_data['json_data'])
                    imported = 0
                    errors = []
                    
                    for task_data in tasks_data:
                        try:
                            Task.objects.create(
                                title=task_data.get('title'),
                                due_date=task_data.get('due_date'),
                                estimated_hours=task_data.get('estimated_hours'),
                                importance=task_data.get('importance'),
                                dependencies=task_data.get('dependencies', '')
                            )
                            imported += 1
                        except Exception as e:
                            errors.append(f"Error importing '{task_data.get('title')}': {str(e)}")
                    
                    if imported > 0:
                        return redirect(f'/?strategy={current_strategy}')
                except json.JSONDecodeError:
                    json_form.add_error('json_data', 'Invalid JSON format')
        
        elif 'delete_task' in request.POST:
            task_id = request.POST.get('task_id')
            Task.objects.filter(id=task_id).delete()
            return redirect(f'/?strategy={current_strategy}')
        
        elif 'toggle_complete' in request.POST:
            task_id = request.POST.get('task_id')
            task = get_object_or_404(Task, id=task_id)
            task.completed = not task.completed
            if task.completed:
                task.completed_at = datetime.now()
            else:
                task.completed_at = None
            task.save()
            return redirect(f'/?strategy={current_strategy}')
        
        elif 'mark_helpful' in request.POST:
            task_id = request.POST.get('task_id')
            helpful = request.POST.get('helpful') == 'true'
            task = get_object_or_404(Task, id=task_id)
            task.was_helpful = helpful
            task.save()
            return redirect(f'/?strategy={current_strategy}')
    
    # Filter tasks
    if show_completed:
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(completed=False)
    
    # Apply prioritization algorithm
    prioritizer = TaskPrioritizer(strategy=current_strategy)
    sorted_tasks = prioritizer.sort_tasks(list(tasks))
    
    # Detect circular dependencies
    cycles = prioritizer.detect_circular_dependencies(sorted_tasks)
    
    # Get statistics
    stats = {
        'total': len(sorted_tasks),
        'overdue': sum(1 for t in sorted_tasks if t.is_overdue()),
        'high_priority': sum(1 for t in sorted_tasks if t.score > 80),
        'quick_wins': sum(1 for t in sorted_tasks if t.estimated_hours <= 2),
        'has_cycles': len(cycles) > 0,
        'cycle_count': len(cycles)
    }
    
    context = {
        'tasks': sorted_tasks,
        'form': TaskForm(),
        'json_form': JSONImportForm(),
        'current_strategy': current_strategy,
        'show_completed': show_completed,
        'stats': stats,
        'cycles': cycles,
        'strategies': TaskPrioritizer(strategy='balanced').strategies.keys()
    }
    
    return render(request, 'tasks/index.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze(request):
    """
    API Endpoint: POST /api/tasks/analyze/
    Accepts list of tasks and returns them sorted by priority.
    """
    try:
        data = json.loads(request.body)
        strategy = data.get('strategy', 'balanced')
        tasks_data = data.get('tasks', [])
        
        if not tasks_data:
            return JsonResponse({'error': 'No tasks provided'}, status=400)
        
        # Validate task data
        required_fields = ['title', 'due_date', 'estimated_hours', 'importance']
        for i, task in enumerate(tasks_data):
            missing = [f for f in required_fields if f not in task]
            if missing:
                return JsonResponse({
                    'error': f'Task {i}: Missing required fields: {", ".join(missing)}'
                }, status=400)
        
        # Initialize prioritizer
        prioritizer = TaskPrioritizer(strategy=strategy)
        
        # Calculate scores
        for task in tasks_data:
            score, components = prioritizer.calculate_score(task, tasks_data)
            task['score'] = score
            task['components'] = components
            
            # Generate explanation
            class TempTask:
                def __init__(self, data):
                    self.title = data['title']
                    self.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                    self.importance = data['importance']
                    self.estimated_hours = data['estimated_hours']
                    self.id = data.get('id', 0)
                
                def days_until_due(self):
                    from datetime import date
                    return (self.due_date - date.today()).days
            
            temp_task = TempTask(task)
            task['explanation'] = prioritizer.generate_explanation(temp_task, components)
        
        # Sort by score
        tasks_data.sort(key=lambda x: x['score'], reverse=True)
        
        return JsonResponse({
            'tasks': tasks_data,
            'strategy': strategy,
            'count': len(tasks_data)
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_suggest(request):
    """
    API Endpoint: GET /api/tasks/suggest/
    Returns top 3 tasks to work on today with explanations.
    """
    try:
        strategy = request.GET.get('strategy', 'balanced')
        
        # Fetch incomplete tasks only
        tasks = Task.objects.filter(completed=False)
        
        if not tasks.exists():
            return JsonResponse({
                'suggested_tasks': [],
                'message': 'No tasks available'
            })
        
        # Initialize prioritizer
        prioritizer = TaskPrioritizer(strategy=strategy)
        
        # Sort tasks
        sorted_tasks = prioritizer.sort_tasks(list(tasks))
        
        # Get top 3
        top_3 = sorted_tasks[:3]
        
        # Serialize response
        response_data = []
        for rank, task in enumerate(top_3, 1):
            response_data.append({
                'rank': rank,
                'id': task.id,
                'title': task.title,
                'due_date': str(task.due_date),
                'estimated_hours': task.estimated_hours,
                'importance': task.importance,
                'score': task.score,
                'explanation': task.explanation,
                'components': task.score_components,
                'is_overdue': task.is_overdue(),
                'days_until_due': task.days_until_due(),
                'has_circular_dependency': task.has_circular_dep
            })
        
        return JsonResponse({
            'suggested_tasks': response_data,
            'strategy': strategy,
            'total_tasks': len(sorted_tasks)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_stats(request):
    """
    API Endpoint: GET /api/tasks/stats/
    Returns statistics about all tasks.
    """
    try:
        tasks = Task.objects.all()
        completed_tasks = tasks.filter(completed=True)
        incomplete_tasks = tasks.filter(completed=False)
        
        # Calculate various statistics
        prioritizer = TaskPrioritizer(strategy='balanced')
        sorted_incomplete = prioritizer.sort_tasks(list(incomplete_tasks))
        
        stats = {
            'total_tasks': tasks.count(),
            'completed': completed_tasks.count(),
            'incomplete': incomplete_tasks.count(),
            'overdue': sum(1 for t in sorted_incomplete if t.is_overdue()),
            'due_today': sum(1 for t in sorted_incomplete if t.days_until_due() == 0),
            'due_this_week': sum(1 for t in sorted_incomplete if 0 <= t.days_until_due() <= 7),
            'high_priority': sum(1 for t in sorted_incomplete if t.score > 80),
            'medium_priority': sum(1 for t in sorted_incomplete if 50 < t.score <= 80),
            'low_priority': sum(1 for t in sorted_incomplete if t.score <= 50),
            'quick_wins': sum(1 for t in sorted_incomplete if t.estimated_hours <= 2),
            'avg_importance': round(sum(t.importance for t in incomplete_tasks) / max(1, incomplete_tasks.count()), 1),
            'total_estimated_hours': sum(t.estimated_hours for t in incomplete_tasks)
        }
        
        return JsonResponse(stats)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_detect_cycles(request):
    """
    API Endpoint: POST /api/tasks/detect-cycles/
    Detects circular dependencies in task list.
    """
    try:
        data = json.loads(request.body)
        tasks_data = data.get('tasks', [])
        
        if not tasks_data:
            return JsonResponse({'cycles': [], 'has_cycles': False})
        
        prioritizer = TaskPrioritizer()
        
        # Convert to temporary objects for cycle detection
        class TempTask:
            def __init__(self, data):
                self.id = data.get('id', data.get('title'))
                self.dependencies = data.get('dependencies', '')
            
            def get_dependency_ids(self):
                if isinstance(self.dependencies, str):
                    return [int(d.strip()) for d in self.dependencies.split(',') if d.strip()]
                return self.dependencies if isinstance(self.dependencies, list) else []
        
        temp_tasks = [TempTask(t) for t in tasks_data]
        cycles = prioritizer.detect_circular_dependencies(temp_tasks)
        
        return JsonResponse({
            'cycles': cycles,
            'has_cycles': len(cycles) > 0,
            'cycle_count': len(cycles)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)