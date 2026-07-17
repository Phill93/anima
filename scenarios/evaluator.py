"""
Scenario Evaluator - Checks for active scenario triggers.

Checks if the user's message contains keywords/conditions defined in ScenarioTriggers.
If a trigger matches, the scenario's context/action is injected into the prompt.
"""
from .models import Scenario, ScenarioTrigger


def check_triggers(user_message: str, session_id: int = None) -> list:
    """
    Check if any scenario triggers match the user message.

    Args:
        user_message: The user's latest message.
        session_id: Optional session ID to filter scenarios (if we add session-scoped scenarios later).

    Returns:
        A list of dicts: {'scenario_name': ..., 'action': ..., 'condition': ...}
    """
    user_msg_lower = user_message.lower()
    triggered_scenarios = []

    # Fetch all active scenarios and their triggers
    scenarios = Scenario.objects.all()
    for scenario in scenarios:
        triggers = scenario.scenario_triggers.all()
        for trigger in triggers:
            condition = trigger.condition.lower()
            # Simple keyword containment check
            if condition in user_msg_lower:
                triggered_scenarios.append({
                    'scenario_name': scenario.name,
                    'scenario_desc': scenario.description,
                    'condition': trigger.condition,
                    'action': trigger.action,
                    'starting_conditions': scenario.starting_conditions,
                })

    return triggered_scenarios
