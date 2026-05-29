from __future__ import annotations
from typing import List, Dict, Optional


class ManifestBuilder:
    """Builds the system prompt for the agent.

    With native function calling, tools are defined in the tools=[...] parameter.
    The system prompt focuses on personality, rules, and context — not action lists.
    """

    def build_system_prompt(self, goal: str,
                            compressed_context: str = "",
                            environment_context: str = "",
                            user_profile: Optional[dict] = None,
                            memory_context: str = "",
                            skill_content: str = "",
                            tool_names: Optional[List[str]] = None) -> str:
        """Build system prompt with personality, rules, and skills."""
        prompt = "You are Zenith, a personal AI companion.\n\n"

        # Task-agnostic execution rules — applies to ALL task types
        prompt += "## How to Respond\n"
        prompt += "- Every user message is a task. Execute it immediately.\n"
        prompt += "- Never ask 'What would you like me to do?' — the user already told you.\n"
        prompt += "- Pick reasonable defaults when uncertain. The user will correct you.\n"
        prompt += "- After completing the task, provide a brief summary and stop.\n\n"

        # Narration style
        prompt += "## Narration\n"
        prompt += "Narrate briefly when using tools: 'Let me check...', 'Reading the file...', 'Now I'll create...'\n"
        prompt += "One sentence per tool batch. Narrate intent, not mechanism.\n\n"

        if user_profile:
            if user_profile.get("name"):
                prompt += f"User: {user_profile['name']}\n"
            if user_profile.get("role"):
                prompt += f"Role: {user_profile['role']}\n"
            if user_profile.get("communication_style"):
                prompt += f"Reply style: {user_profile['communication_style']}\n"
            if user_profile.get("preferences"):
                for pref in user_profile["preferences"]:
                    prompt += f"- {pref}\n"
            prompt += "\n"

        if tool_names:
            prompt += "Tools: " + ", ".join(tool_names) + "\n\n"


        if skill_content:
            prompt += f"\n{skill_content}"

        if environment_context:
            prompt += f"\nEnvironment: {environment_context}"

        if memory_context:
            prompt += f"\nRelevant memory: {memory_context}"

        if compressed_context:
            prompt += f"\nConversation context: {compressed_context}"

        return prompt
