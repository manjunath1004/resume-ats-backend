# ✅ Refined backend code for 90%+ ATS resume analysis

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from io import BytesIO
import pdfplumber
import re
import uuid
import os
from supabase import create_client
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "resumes")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ✅ FastAPI instance
app = FastAPI()

# ✅ CORS config (replace with your frontend domain if known)
origins = [
    "http://localhost:3000",
    "https://your-frontend-url.vercel.app"  # 🔁 Replace with actual deployed frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Root path to avoid 404 on base URL
@app.get("/")
def root():
    return {"message": "✅ Resume ATS backend is live!"}

# ✅ Health check route for Render
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

# ✅ Keyword categories
CATEGORY_KEYWORDS = {
    "technical": ["python", "java", "c++", "javascript", "react", "nodejs", "django", "flask", "html", "css", "sql", "mongodb", "mysql", "git", "github", "linux", "aws", "docker", "kubernetes"],
    "uiux": ["figma", "adobe xd", "photoshop", "illustrator", "ux", "ui", "wireframing", "branding", "canva", "visual design"],
    "business": ["seo", "sem", "content marketing", "social media", "facebook ads", "google ads", "email marketing", "analytics", "brand development", "project management", "digital marketing"]
}

ALL_KEYWORDS = [kw for lst in CATEGORY_KEYWORDS.values() for kw in lst]
SECTION_HEADERS = ["summary", "education", "experience", "projects", "skills", "certifications", "achievements"]

# ✅ Resume upload + parsing endpoint
@app.post("/api/parse-resume")
async def parse_resume(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.pdf"

        # ✅ Upload to Supabase
        upload_response = supabase.storage.from_(SUPABASE_BUCKET).upload(
            filename, contents, {"content-type": "application/pdf"}
        )

        if hasattr(upload_response, "error") and upload_response.error:
            raise Exception(f"Supabase upload error: {upload_response.error.message}")

        # ✅ Extract text from PDF
        with pdfplumber.open(BytesIO(contents)) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        name = lines[0] if 1 <= len(lines[0].split()) <= 4 else "Not Detected"

        education = "Detected" if re.search(r"\b(bachelor|master|education|degree)\b", text, re.I) else "Not Detected"

        experience_keywords = ["experience", "years", "worked", "intern", "project", "developed"]
        experience_found = any(word in text.lower() for word in experience_keywords)
        experience = "Detected" if experience_found else "Not Detected"

        matched_keywords = [kw for kw in ALL_KEYWORDS if kw.lower() in text.lower()]
        skill_score = int((len(matched_keywords) / len(ALL_KEYWORDS)) * 100)

        matched_by_category = {
            cat: [kw for kw in kws if kw.lower() in text.lower()]
            for cat, kws in CATEGORY_KEYWORDS.items()
        }

        present_sections = [sec for sec in SECTION_HEADERS if sec in text.lower()]
        missing_sections = list(set(SECTION_HEADERS) - set(present_sections))
        section_score = int((len(present_sections) / len(SECTION_HEADERS)) * 100)

        ats_score = int((skill_score * 0.6) + (section_score * 0.4))

        suggestions = []
        if skill_score < 60:
            suggestions.append("Include more technical and role-specific keywords to boost your ATS ranking.")
        if "summary" not in present_sections:
            suggestions.append("Add a professional summary at the top of your resume.")
        if "projects" not in present_sections:
            suggestions.append("Include relevant projects to demonstrate your practical experience.")
        if len(matched_keywords) < 8:
            suggestions.append("Mention more tools or platforms like Git, Figma, or AWS.")
        if education == "Not Detected":
            suggestions.append("Clearly specify your educational background.")
        if experience == "Not Detected":
            suggestions.append("Add work experience, internships, or personal projects.")
        if "skills" not in present_sections:
            suggestions.append("Include a dedicated skills section listing your tools and technologies.")

        return {
            "file_url": f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}",
            "name": name,
            "education": education,
            "experience": experience,
            "skills": matched_keywords,
            "matched_by_category": matched_by_category,
            "ats_score": ats_score,
            "ats_score_breakdown": {
                "skill_score": skill_score,
                "section_score": section_score
            },
            "missing_sections": missing_sections,
            "suggestions": suggestions
        }

    except Exception as e:
        print("❌ Backend error:", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)
