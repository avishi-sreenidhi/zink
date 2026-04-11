"""
Screening Tools: Structured tool definitions
Fixed: Model ID to gemini-2.5-flash-lite & removed redundant model_dump().
"""

import os
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.tools import StructuredTool
from dotenv import load_dotenv

from models import ResumeExtraction, CandidateScore
from integrations import ExcelManager, EmailManager

load_dotenv()

USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"

class ScreeningTools:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE API KEY NOT FOUND in .env")

        if USE_OLLAMA:
            self.llm = ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                format="json",
                temperature=0
            )
        else:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not in .env")

            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=api_key,
                temperature=0
            )

        self.excel = ExcelManager()
        self.email = EmailManager()

        # Expose as LangChain StructuredTools so GovernedTool can wrap them
        self.extract_resume = StructuredTool.from_function(
            func=self._extract_resume,
            name="extract_resume",
            description="Extract structured data from resume text."
        )
        self.score_candidate = StructuredTool.from_function(
            func=self._score_candidate,
            name="score_candidate",
            description="Score a candidate based on extracted resume data."
        )
        self.log_to_excel_tool = StructuredTool.from_function(
            func=self._log_to_excel,
            name="log_to_excel_tool",
            description="Log candidate screening result to Excel."
        )
        self.send_email_tool = StructuredTool.from_function(
            func=self._send_email,
            name="send_email_tool",
            description="Send screening outcome email to candidate."
        )

    def _extract_resume(self, resume_text: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract resume details. Return JSON matching the schema."),
            ("human", "Resume:\n\n{resume_text}")
        ])
        parser = JsonOutputParser(pydantic_object=ResumeExtraction)
        chain = prompt | self.llm | parser

        result = chain.invoke({"resume_text": resume_text})

        email = result.get("email") or result.get("email_address")
        if isinstance(email, list):
            result["email"] = email[0] if email else "unknown"

        skills = result.get("skills", [])
        if isinstance(skills, dict):
            flat = []
            for v in skills.values():
                if isinstance(v, list):
                    flat.extend(str(s) for s in v)
                else:
                    flat.append(str(v))
            result["skills"] = flat
        elif isinstance(skills, list):
            result["skills"] = [s if isinstance(s, str) else str(s) for s in skills]

        education = result.get("education", "")
        if isinstance(education, list):
            parts = []
            for e in education:
                if isinstance(e, dict):
                    parts.append(e.get("degree") or e.get("field") or str(e))
                else:
                    parts.append(str(e))
            result["education"] = ", ".join(parts) if parts else ""
        elif isinstance(education, dict):
            result["education"] = education.get("degree") or education.get("field") or str(education)

        print(f"✓ Extracted: {result.get('name', 'Unknown')}")
        return result

    def _score_candidate(self, name: str, years_experience: int, skills: list[str], education: str) -> dict:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Form an apt rubric for a Entry Level Software Engineer role and Score candidate 0-1. Return JSON: score, reasoning, strengths, weaknesses."),
            ("human", "Name: {name}, Years: {years_experience}, Skills: {skills_string}, Ed: {education}")
        ])

        parser = JsonOutputParser(pydantic_object=CandidateScore)
        chain = prompt | self.llm | parser

        result = chain.invoke({
            "name": name,
            "years_experience": years_experience,
            "skills_string": ', '.join(skills) if isinstance(skills, list) else str(skills),
            "education": education
        })

        llm_reasoning = result.get("reasoning", "")
        strengths = [s if isinstance(s, str) else str(s) for s in result.get("strengths", [])]
        weaknesses = [w if isinstance(w, str) else str(w) for w in result.get("weaknesses", [])]

        reasoning_fragment = f"{llm_reasoning} | Strengths: {', '.join(strengths) if strengths else 'none'} | Weaknesses: {', '.join(weaknesses) if weaknesses else 'none'}"

        return {
            "score": result.get("score"),
            "reasoning": reasoning_fragment,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "raw_result": result
        }

    def _log_to_excel(self, candidate_id: str, name: str, email: str, score: float, decision: str) -> dict:
        self.excel.add_candidate(candidate_id, name, email)
        self.excel.update_screening_score(candidate_id, score, decision)
        return {"logged": True, "candidate_id": candidate_id}

    def _send_email(self, candidate_email: str, candidate_name: str, decision: str, score: float) -> dict:
        if decision == "reject":
            self.email.send_rejection(candidate_email, candidate_name, "Experience mismatch.")
        else:
            self.email.send_screening_passed(candidate_email, candidate_name, "Moving to interviews.")
        return {"sent": True, "recipient": candidate_email}