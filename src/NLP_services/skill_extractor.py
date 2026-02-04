
import spacy
import re
from typing import Dict, List, Any

# Attempt to load the model, or lazy load it later to avoid import errors if not installed immediately
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("spaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")
    nlp = None

class SkillExtractorService:
    @staticmethod
    def extract_details(text: str) -> Dict[str, Any]:
        if not nlp:
             # Fallback or error if model missing
             raise RuntimeError("NLP Model not loaded")

        doc = nlp(text)
        
        return {
            "skills": SkillExtractorService._extract_skills(text, doc),
            "experience_level": SkillExtractorService._extract_experience_level(text),
            "education": SkillExtractorService._extract_education(text),
            "entities": SkillExtractorService._extract_entities(doc)
        }

    @staticmethod
    def _extract_skills(text: str, doc) -> Dict[str, List[Dict[str, float]]]:
        # This is a simplified skill extraction. 
        # In a real app, we would have a large database of skills to match against.
        # Here we will match against a small sample list and use NER for others.
        
        common_skills = [
            "Python", "Java", "C++", "JavaScript", "React", "Node.js", "AWS", "Docker", "Kubernetes",
            "SQL", "NoSQL", "Machine Learning", "AI", "Data Science", "Git", "CI/CD",
            "Communication", "Leadership", "Problem Solving", "Teamwork"
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in common_skills:
            if skill.lower() in text_lower:
                found_skills.append({"name": skill, "weight": 1.0})
        
        return {
            "must_have": found_skills,
            "good_to_have": [] # Logic to distinguish could be added later based on "required", "preferred" keywords
        }

    @staticmethod
    def _extract_experience_level(text: str) -> str | None:
        # Regex for finding years of experience
        # e.g. "5+ years", "3-5 years", "2 years"
        pattern = r"(\d+(?:\+)?(?:\s*-\s*\d+)?)\s*years?"
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if matches:
            # Return the first match, or logic to find the max
            return f"{matches[0]} years experience"
        
        return None

    @staticmethod
    def _extract_education(text: str) -> Dict[str, List[str]]:
        education_keywords = [
            "Bachelor", "Master", "PhD", "B.Sc", "M.Sc", "B.Tech", "M.Tech", 
            "Computer Science", "Engineering", "Degree"
        ]
        
        found_edu = []
        sentences = text.split('\n') 
        for line in sentences:
            for kw in education_keywords:
                if kw.lower() in line.lower():
                    found_edu.append(line.strip())
                    break
        
        return {"requirements": found_edu[:3]} 

    @staticmethod
    def _extract_entities(doc) -> List[str]:
        # Extract ORG, PRODUCT from spaCy
        entities = []
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT", "WORK_OF_ART"]:
                entities.append(ent.text)
        return list(set(entities))
