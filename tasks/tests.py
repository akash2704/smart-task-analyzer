from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from .models import Task
from .services import TaskPrioritizer, AdaptivePrioritizer
import json


class TaskModelTests(TestCase):
    """Test cases for Task model validation and methods."""
    
    def setUp(self):
        """Set up test data."""
        self.valid_task = Task.objects.create(
            title="Test Task",
            due_date=date.today() + timedelta(days=7),
            estimated_hours=5.0,
            importance=8,
            dependencies=""
        )
    
    def test_task_creation(self):
        """Test basic task creation."""
        self.assertEqual(self.valid_task.title, "Test Task")
        self.assertEqual(self.valid_task.importance, 8)
        self.assertEqual(self.valid_task.estimated_hours, 5.0)
    
    def test_task_string_representation(self):
        """Test __str__ method."""
        self.assertIn("Test Task", str(self.valid_task))
    
    def test_is_overdue(self):
        """Test overdue detection."""
        # Not overdue
        self.assertFalse(self.valid_task.is_overdue())
        
        # Make it overdue
        overdue_task = Task.objects.create(
            title="Overdue Task",
            due_date=date.today() - timedelta(days=5),
            estimated_hours=2.0,
            importance=7
        )
        self.assertTrue(overdue_task.is_overdue())
    
    def test_days_until_due(self):
        """Test days calculation."""
        days = self.valid_task.days_until_due()
        self.assertEqual(days, 7)
        
        # Overdue task
        overdue_task = Task.objects.create(
            title="Overdue",
            due_date=date.today() - timedelta(days=3),
            estimated_hours=1.0,
            importance=5
        )
        self.assertEqual(overdue_task.days_until_due(), -3)
    
    def test_get_dependency_ids(self):
        """Test dependency parsing."""
        task_with_deps = Task.objects.create(
            title="Dependent Task",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies="1,2,3"
        )
        self.assertEqual(task_with_deps.get_dependency_ids(), [1, 2, 3])
        
        # Empty dependencies
        self.assertEqual(self.valid_task.get_dependency_ids(), [])
    
    def test_invalid_estimated_hours(self):
        """Test validation for invalid hours."""
        from django.core.exceptions import ValidationError
        
        with self.assertRaises(ValidationError):
            invalid_task = Task(
                title="Invalid",
                due_date=date.today(),
                estimated_hours=-5,  # Invalid
                importance=5
            )
            invalid_task.full_clean()
    
    def test_invalid_importance(self):
        """Test validation for invalid importance."""
        from django.core.exceptions import ValidationError
        
        with self.assertRaises(ValidationError):
            invalid_task = Task(
                title="Invalid",
                due_date=date.today(),
                estimated_hours=1.0,
                importance=15  # Out of range
            )
            invalid_task.full_clean()


class TaskPrioritizerTests(TestCase):
    """Test cases for TaskPrioritizer algorithm."""
    
    def setUp(self):
        """Set up test data."""
        self.prioritizer = TaskPrioritizer(strategy='balanced')
        
        # Create test tasks
        self.urgent_task = Task.objects.create(
            title="Urgent Task",
            due_date=date.today() + timedelta(days=1),
            estimated_hours=2.0,
            importance=9
        )
        
        self.important_task = Task.objects.create(
            title="Important Task",
            due_date=date.today() + timedelta(days=14),
            estimated_hours=10.0,
            importance=10
        )
        
        self.quick_task = Task.objects.create(
            title="Quick Task",
            due_date=date.today() + timedelta(days=30),
            estimated_hours=0.5,
            importance=5
        )
        
        self.overdue_task = Task.objects.create(
            title="Overdue Task",
            due_date=date.today() - timedelta(days=2),
            estimated_hours=3.0,
            importance=7
        )
    
    def test_urgency_score_calculation(self):
        """Test urgency scoring logic."""
        # Due tomorrow
        urgency = self.prioritizer.calculate_urgency_score(date.today() + timedelta(days=1))
        self.assertGreater(urgency, 89)
        
        # Overdue
        urgency_overdue = self.prioritizer.calculate_urgency_score(date.today() - timedelta(days=2))
        self.assertGreater(urgency_overdue, 100)
        
        # Far future
        urgency_far = self.prioritizer.calculate_urgency_score(date.today() + timedelta(days=60))
        self.assertLess(urgency_far, 50)
    
    def test_importance_score_calculation(self):
        """Test importance scoring."""
        self.assertEqual(self.prioritizer.calculate_importance_score(10), 100)
        self.assertEqual(self.prioritizer.calculate_importance_score(5), 50)
        self.assertEqual(self.prioritizer.calculate_importance_score(1), 10)
    
    def test_effort_score_calculation(self):
        """Test effort scoring (inverse relationship)."""
        # Quick task gets high score
        quick_score = self.prioritizer.calculate_effort_score(0.5)
        self.assertGreater(quick_score, 80)
        
        # Long task gets low score
        long_score = self.prioritizer.calculate_effort_score(20)
        self.assertLess(long_score, 30)
        
        # Zero hours should return 0
        zero_score = self.prioritizer.calculate_effort_score(0)
        self.assertEqual(zero_score, 0)
    
    def test_dependency_score_calculation(self):
        """Test dependency scoring."""
        # Create tasks with dependencies
        blocking_task = Task.objects.create(
            title="Blocking Task",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5
        )
        
        dependent_1 = Task.objects.create(
            title="Dependent 1",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies=str(blocking_task.id)
        )
        
        dependent_2 = Task.objects.create(
            title="Dependent 2",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies=str(blocking_task.id)
        )
        
        all_tasks = [blocking_task, dependent_1, dependent_2]
        dep_score = self.prioritizer.calculate_dependency_score(blocking_task, all_tasks)
        
        # Should be 30 (2 blocked tasks × 15 points each)
        self.assertEqual(dep_score, 30)
    
    def test_balanced_strategy_scoring(self):
        """Test balanced strategy weighs all factors."""
        tasks = [self.urgent_task, self.important_task, self.quick_task, self.overdue_task]
        
        for task in tasks:
            t_data = {
                'id': task.id,
                'due_date': task.due_date,
                'importance': task.importance,
                'estimated_hours': task.estimated_hours
            }
            score, components = self.prioritizer.calculate_score(t_data, tasks)
            task.score = score
        
        # Overdue task should score highest
        self.assertGreater(self.overdue_task.score, self.important_task.score)
    
    def test_deadline_strategy(self):
        """Test deadline-driven strategy prioritizes urgency."""
        deadline_prioritizer = TaskPrioritizer(strategy='deadline')
        
        tasks = [self.urgent_task, self.important_task, self.quick_task]
        sorted_tasks = deadline_prioritizer.sort_tasks(tasks)
        
        # Urgent task should be first
        self.assertEqual(sorted_tasks[0].title, "Urgent Task")
    
    def test_quick_wins_strategy(self):
        """Test quick wins strategy prioritizes low effort."""
        quick_prioritizer = TaskPrioritizer(strategy='quick_wins')
        
        tasks = [self.urgent_task, self.important_task, self.quick_task]
        sorted_tasks = quick_prioritizer.sort_tasks(tasks)
        
        # Quick task should rank high
        self.assertIn(self.quick_task, sorted_tasks[:2])
    
    def test_impact_strategy(self):
        """Test impact strategy prioritizes importance."""
        impact_prioritizer = TaskPrioritizer(strategy='impact')
        
        tasks = [self.urgent_task, self.important_task, self.quick_task]
        sorted_tasks = impact_prioritizer.sort_tasks(tasks)
        
        # Important task (importance=10) should be first
        self.assertEqual(sorted_tasks[0].title, "Important Task")
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        # Create circular dependency: A -> B -> C -> A
        task_a = Task.objects.create(
            title="Task A",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies=""
        )
        
        task_b = Task.objects.create(
            title="Task B",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies=str(task_a.id)
        )
        
        task_c = Task.objects.create(
            title="Task C",
            due_date=date.today(),
            estimated_hours=1.0,
            importance=5,
            dependencies=str(task_b.id)
        )
        
        # Create the cycle
        task_a.dependencies = str(task_c.id)
        task_a.save()
        
        tasks = [task_a, task_b, task_c]
        cycles = self.prioritizer.detect_circular_dependencies(tasks)
        
        # Should detect at least one cycle
        self.assertGreater(len(cycles), 0)
    
    def test_sort_tasks_attaches_metadata(self):
        """Test that sort_tasks attaches score and explanation."""
        tasks = [self.urgent_task, self.important_task]
        sorted_tasks = self.prioritizer.sort_tasks(tasks)
        
        for task in sorted_tasks:
            self.assertTrue(hasattr(task, 'score'))
            self.assertTrue(hasattr(task, 'explanation'))
            self.assertTrue(hasattr(task, 'score_components'))
    
    def test_business_days_calculation(self):
        """Test business day calculation excludes weekends."""
        # Monday to Friday = 5 business days
        monday = date(2025, 1, 6)  # A Monday
        friday = date(2025, 1, 10)  # Same week Friday
        
        business_days = self.prioritizer._calculate_business_days(monday, friday)
        self.assertEqual(business_days, 5)
        
        # Including weekend
        next_monday = date(2025, 1, 13)
        business_days_with_weekend = self.prioritizer._calculate_business_days(monday, next_monday)
        self.assertEqual(business_days_with_weekend, 6)  # Mon-Fri + Mon


class APIEndpointTests(TestCase):
    """Test cases for API endpoints."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = Client()
        
        self.task_data = {
            'title': 'API Test Task',
            'due_date': str(date.today() + timedelta(days=7)),
            'estimated_hours': 3.0,
            'importance': 8,
            'dependencies': ''
        }
    
    def test_api_analyze_endpoint(self):
        """Test POST /api/tasks/analyze/ endpoint."""
        url = reverse('tasks:api_analyze')
        
        payload = {
            'strategy': 'balanced',
            'tasks': [self.task_data]
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('tasks', data)
        self.assertEqual(len(data['tasks']), 1)
        self.assertIn('score', data['tasks'][0])
        self.assertIn('explanation', data['tasks'][0])
    
    def test_api_analyze_missing_fields(self):
        """Test API validation for missing fields."""
        url = reverse('tasks:api_analyze')
        
        invalid_payload = {
            'strategy': 'balanced',
            'tasks': [{'title': 'Incomplete Task'}]  # Missing required fields
        }
        
        response = self.client.post(
            url,
            data=json.dumps(invalid_payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
    
    def test_api_suggest_endpoint(self):
        """Test GET /api/tasks/suggest/ endpoint."""
        # Create some tasks
        Task.objects.create(
            title="Task 1",
            due_date=date.today() + timedelta(days=1),
            estimated_hours=2.0,
            importance=9
        )
        Task.objects.create(
            title="Task 2",
            due_date=date.today() + timedelta(days=7),
            estimated_hours=5.0,
            importance=6
        )
        
        url = reverse('tasks:api_suggest')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('suggested_tasks', data)
        self.assertLessEqual(len(data['suggested_tasks']), 3)
        
        # Check structure of suggestions
        if data['suggested_tasks']:
            first_suggestion = data['suggested_tasks'][0]
            self.assertIn('rank', first_suggestion)
            self.assertIn('title', first_suggestion)
            self.assertIn('score', first_suggestion)
            self.assertIn('explanation', first_suggestion)
    
    def test_api_stats_endpoint(self):
        """Test GET /api/tasks/stats/ endpoint."""
        # Create test tasks
        Task.objects.create(
            title="Active Task",
            due_date=date.today() + timedelta(days=5),
            estimated_hours=3.0,
            importance=7,
            completed=False
        )
        Task.objects.create(
            title="Completed Task",
            due_date=date.today() - timedelta(days=2),
            estimated_hours=2.0,
            importance=5,
            completed=True
        )
        
        url = reverse('tasks:api_stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('total_tasks', data)
        self.assertIn('completed', data)
        self.assertIn('incomplete', data)
        self.assertEqual(data['total_tasks'], 2)
        self.assertEqual(data['completed'], 1)
        self.assertEqual(data['incomplete'], 1)


class AdaptivePrioritizerTests(TestCase):
    """Test cases for machine learning-enhanced prioritizer."""
    
    def test_weight_adjustment_from_feedback(self):
        """Test that weights adjust based on user feedback."""
        # Create feedback history (rejecting urgent tasks)
        feedback = [
            ({'urgency_score': 95, 'importance': 5}, False),
            ({'urgency_score': 90, 'importance': 6}, False),
            ({'urgency_score': 92, 'importance': 7}, False),
            ({'urgency_score': 88, 'importance': 8}, False),
            ({'urgency_score': 91, 'importance': 5}, False),
            ({'urgency_score': 89, 'importance': 6}, False),
        ]
        
        adaptive = AdaptivePrioritizer(strategy='balanced', feedback_history=feedback)
        adjusted_weights = adaptive.adjust_weights_from_feedback()
        
        # Urgency weight should be reduced
        original_urgency_weight = adaptive.strategies['balanced'][0]
        self.assertLess(adjusted_weights[0], original_urgency_weight)


class EdgeCaseTests(TestCase):
    """Test edge cases and error handling."""
    
    def test_zero_estimated_hours(self):
        """Test handling of zero estimated hours."""
        prioritizer = TaskPrioritizer()
        effort_score = prioritizer.calculate_effort_score(0)
        self.assertEqual(effort_score, 0)
    
    def test_very_large_estimated_hours(self):
        """Test handling of unrealistically large hours."""
        prioritizer = TaskPrioritizer()
        effort_score = prioritizer.calculate_effort_score(1000)
        self.assertGreaterEqual(effort_score, 0)
    
    def test_far_future_due_date(self):
        """Test scoring for tasks far in the future."""
        prioritizer = TaskPrioritizer()
        far_future = date.today() + timedelta(days=365)
        urgency = prioritizer.calculate_urgency_score(far_future)
        self.assertGreaterEqual(urgency, 0)
    
    def test_empty_task_list(self):
        """Test sorting empty task list."""
        prioritizer = TaskPrioritizer()
        sorted_tasks = prioritizer.sort_tasks([])
        self.assertEqual(len(sorted_tasks), 0)