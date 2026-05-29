"""Skill loader — discovers and loads SKILL.md files.

LLM decides which skills to use based on descriptions.
Uses load_skill tool to request full content on demand.
No semantic search — the LLM is the matcher.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class Skill:
    def __init__(self, name: str, description: str, content: str, path: Path,
                 internal: bool = False):
        self.name = name
        self.description = description
        self.content = content
        self.path = path
        self.internal = internal


class SkillLoader:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}

    def load_all(self):
        """Discover and load all SKILL.md files."""
        if not self.skills_dir.exists():
            return
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                raw = skill_file.read_text(encoding="utf-8")
                name, description, content, internal = self._parse_skill(raw, skill_file)
                if name:
                    self._skills[name] = Skill(name, description, content, skill_file,
                                                internal=internal)
            except Exception:
                continue
        log.info(f"SkillLoader: loaded {len(self._skills)} skills")

    def _parse_skill(self, raw: str, path: Path) -> tuple:
        """Parse SKILL.md frontmatter + content."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', raw, re.DOTALL)
        if not match:
            return path.parent.name, "", raw, False
        frontmatter = match.group(1)
        content = match.group(2)
        name_match = re.search(r'name:\s*(.+)', frontmatter)
        desc_match = re.search(r'description:\s*(.+)', frontmatter)
        internal_match = re.search(r'internal:\s*(true|false)', frontmatter, re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else path.parent.name
        description = desc_match.group(1).strip() if desc_match else ""
        internal = bool(internal_match and internal_match.group(1).lower() == "true")
        return name, description, content, internal

    def get_all_content(self) -> str:
        """Return public skill descriptions for system prompt.

        Internal skills are hidden from descriptions but still loadable via load_skill.
        """
        if not self._skills:
            return ""
        desc_parts = []
        for skill in self._skills.values():
            if skill.internal:
                continue
            desc_parts.append(f"- **{skill.name}**: {skill.description}")
        return "Available skills:\n" + "\n".join(desc_parts) + \
               "\n\nUse load_skill(name) to read a skill's full content before following it."

    def load_skill_content(self, name: str) -> str:
        """Return full content of a single skill by name."""
        skill = self._skills.get(name)
        if not skill:
            for sname, skill_obj in self._skills.items():
                if name.lower() in sname.lower():
                    skill = skill_obj
                    break
        if not skill:
            available = ", ".join(self._skills.keys())
            return f"Skill '{name}' not found. Available: {available}"
        return f"## {skill.name}\n{skill.content}"

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
