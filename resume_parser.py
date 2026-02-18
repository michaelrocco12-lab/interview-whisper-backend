import re
from typing import Dict, List

def parse_resume(text: str) -> Dict:
    skills = extract_skills(text)
    experience = extract_experience(text)
    education = extract_education(text)
    return {
        "raw_text": text,
        "skills": skills,
        "experience": experience,
        "education": education,
        "summary": text[:500]
    }

def extract_skills(text: str) -> List[str]:
    skill_patterns = [
        r'\b(Python|JavaScript|Java|C\+\+|Ruby|Go|Rust|TypeScript)\b',
        r'\b(React|Vue|Angular|Node\.js|Django|Flask|FastAPI)\b',
        r'\b(AWS|Azure|GCP|Docker|Kubernetes|Terraform)\b',
        r'\b(SQL|PostgreSQL|MongoDB|Redis|MySQL)\b',
        r'\b(Git|CI/CD|Agile|Scrum|TDD)\b',
        r'\b(Machine Learning|AI|Data Science|NLP)\b'
    ]
    skills = set()
    for pattern in skill_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        skills.update(matches)
    return list(skills)

def extract_experience(text: str) -> List[Dict]:
    experience_pattern = r'(\d{4})\s*[-–]\s*(\d{4}|Present|Current)'
    matches = re.finditer(experience_pattern, text, re.IGNORECASE)
    experiences = []
    for match in matches:
        start_year = match.group(1)
        end_year = match.group(2)
        start_pos = max(0, match.start() - 100)
        end_pos = min(len(text), match.end() + 100)
        context = text[start_pos:end_pos].strip()
        experiences.append({"period": f"{start_year}-{end_year}", "context": context})
    return experiences

def extract_education(text: str) -> List[str]:
    education_keywords = [
        r'\b(Bachelor|Master|PhD|B\.S\.|M\.S\.|MBA)\b',
        r'\b(University|College|Institute)\b'
    ]
    education = []
    for pattern in education_keywords:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            start_pos = max(0, match.start() - 50)
            end_pos = min(len(text), match.end() + 50)
            context = text[start_pos:end_pos].strip()
            if context not in education:
                education.append(context)
    return education