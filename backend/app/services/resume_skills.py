
import re

SKILL_CATALOG = {
    "Python": ["python"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "React": ["react", "reactjs"],
    "Node.js": ["node.js", "nodejs"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQL": ["sql"],
    "Docker": ["docker"],
    "Git": ["git"],
    "GitHub": ["github"],
    "AWS": ["aws"],
    "Azure": ["azure"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "Machine Learning": ["machine learning"],
    "Data Analysis": ["data analysis"],
    "REST API": ["rest api", "restful api"],
}


def extract_skills(text: str) -> list[str]:
    detected = []

    for canonical_name, aliases in SKILL_CATALOG.items():
        for alias in aliases:
            pattern = (
                r"(?<![A-Za-z0-9])"
                + re.escape(alias)
                + r"(?![A-Za-z0-9])"
            )

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                detected.append(canonical_name)
                break

    return detected
