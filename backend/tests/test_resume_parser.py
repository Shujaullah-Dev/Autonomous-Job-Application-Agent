from datetime import date
from pathlib import Path
from app.services.resume_contact import extract_contact
from app.services.resume_parser import extract_resume_text
from app.services.resume_sections import extract_experiences, extract_educations
from app.services.resume_skills import extract_skills

REALISTIC = '''SHUJAULLAH ZAHID
shujazahid094@gmail.com• +92-3310096999• Haripur
TECHNICAL SKILLS
Python, PyTorch, TensorFlow, FastAPI, OpenCV, YOLO
WORK EXPERIENCE
Sybrid Pvt Ltd, Islamabad — AI Intern Jun 2025 – Aug 2025
Worked on SAR data.
BraineX World, Abbottabad — Python Developer Jun 2022 – Aug 2022
Developed scripts.
EDUCATION
Bachelor of Science in Artificial Intelligence (BS AI) 2022 – 2026
Pak-Austria Fachhochschule: Institute of Applied Sciences and Technology (PAF-IAST), Haripur, KPK
F.Sc — Pre-Engineering 2020 – 2022
The Peace Group of College, Haripur, KPK
Matriculation 2019 – 2020
Crescent School and College, Karachi, Sindh
FEATURED PROJECTS
Rice Crop Health Monitoring System 2025 – 2026
LANGUAGES
English: Intermediate
'''


def test_realistic_resume():
    contact = extract_contact(REALISTIC)
    assert contact.phone == '+92-3310096999'
    assert contact.email == 'shujazahid094@gmail.com'
    experiences = extract_experiences(REALISTIC)
    assert len(experiences) == 2
    assert experiences[0].company_name == 'Sybrid Pvt Ltd, Islamabad'
    assert experiences[0].job_title == 'AI Intern'
    assert experiences[0].start_date == date(2025, 6, 1)
    educations = extract_educations(REALISTIC)
    assert len(educations) == 3
    assert educations[0].degree.startswith('Bachelor of Science')
    assert 'PyTorch' in extract_skills(REALISTIC)


def test_original_labeled_resume():
    text = '''EXPERIENCE
Job Title: Backend Developer
Company: Example Technologies
Start: 2023-01
End: Present
EDUCATION
Institution: Example University
Degree: BS Computer Science
Start: 2019-09
End: 2023-06'''
    assert len(extract_experiences(text)) == 1
    assert len(extract_educations(text)) == 1


def test_unlabeled_nonphone_is_rejected():
    assert extract_contact('Completed 1234567890 transactions').phone is None


def test_uploaded_pdf_when_available():
    fixture = Path(__file__).parent / 'fixtures' / 'real_resume.pdf'
    if not fixture.exists():
        return
    text = extract_resume_text(fixture.read_bytes(), 'pdf')
    assert len(extract_experiences(text)) == 2
    assert len(extract_educations(text)) == 3
