from datetime import date, datetime

class TaskPrioritizer:
    def __init__(self, strategy='balanced'):
        # Weights: (Urgency, Importance, Effort)
        self.strategies = {
            'balanced': (0.4, 0.4, 0.2),
            'deadline': (0.8, 0.1, 0.1),
            'quick_wins': (0.1, 0.1, 0.8), # Prioritize low effort
            'impact': (0.1, 0.9, 0.0)      # Prioritize importance
        }
        self.weights = self.strategies.get(strategy, self.strategies['balanced'])

    def calculate_score(self, task_dict):
        # 1. Calculate Urgency (0-100)
        due = datetime.strptime(str(task_dict['due_date']), "%Y-%m-%d").date()
        days_left = (due - date.today()).days
        
        if days_left < 0:
            s_urgency = 100 + (abs(days_left) * 5) # Overdue penalty
        else:
            s_urgency = max(0, 100 - (days_left * 5))

        # 2. Calculate Importance (0-100)
        s_importance = int(task_dict['importance']) * 10

        # 3. Calculate Effort (0-100) -> Inverted: Less time = More points
        hours = float(task_dict['estimated_hours'])
        s_effort = min(100, (1 / max(0.5, hours)) * 50)

        # 4. Apply Strategy Weights
        w_urg, w_imp, w_eff = self.weights
        
        raw_score = (s_urgency * w_urg) + (s_importance * w_imp) + (s_effort * w_eff)
        return round(raw_score, 1)

    def sort_tasks(self, tasks):
        # Attach score to each task object temporarily
        for task in tasks:
            # Convert model instance to dict for calculation
            t_data = {
                'due_date': task.due_date, 
                'importance': task.importance, 
                'estimated_hours': task.estimated_hours
            }
            task.score = self.calculate_score(t_data)
            
            # Explanation Logic (Bonus points for UX)
            if task.score > 80: task.explanation = "Critical Priority: Do Immediately"
            elif task.score > 50: task.explanation = "Moderate Priority: Schedule soon"
            else: task.explanation = "Low Priority: Backlog"
            
        return sorted(tasks, key=lambda t: t.score, reverse=True)