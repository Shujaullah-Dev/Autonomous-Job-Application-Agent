import re
from datetime import date
from app.schemas.resume_analysis import ResumeEducation, ResumeExperience

HEADINGS = {
    'EXPERIENCE': 'experience', 'WORK EXPERIENCE': 'experience',
    'PROFESSIONAL EXPERIENCE': 'experience', 'EMPLOYMENT HISTORY': 'experience',
    'EDUCATION': 'education', 'ACADEMIC BACKGROUND': 'education',
    'EDUCATIONAL BACKGROUND': 'education',
}
STOP_HEADINGS = {
    'PROFESSIONAL SUMMARY', 'SUMMARY', 'PROFILE', 'TECHNICAL SKILLS',
    'SKILLS', 'FEATURED PROJECTS', 'PROJECTS', 'PERSONAL PROJECTS',
    'LANGUAGES', 'CERTIFICATIONS', 'AWARDS', 'INTERESTS', 'REFERENCES',
    'PUBLICATIONS', 'VOLUNTEERING',
}
MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
MONTH_TOKEN = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE_TOKEN = rf'(?:\d{{4}}-\d{{2}}|{MONTH_TOKEN}\.?\s+\d{{4}}|\d{{4}}|Present|Current|Ongoing)'
RANGE_RE = re.compile(rf'(?P<start>{DATE_TOKEN})\s*[-–—]\s*(?P<end>{DATE_TOKEN})\s*$', re.I)
EXP_RE = re.compile(r'^(?P<company>.+?)\s+[—–]\s+(?P<role>.+)$')
DEGREE_RE = re.compile(r'^(?:Bachelor|Master|Doctor|Ph\.?D|BS\b|BSc\b|MS\b|MSc\b|F\.?Sc\b|Matriculation\b|Intermediate\b|Diploma\b)', re.I)
FIELDS = {'experience': {'job title', 'company', 'start', 'end'},
          'education': {'institution', 'degree', 'start', 'end'}}


def parse_month(value: str) -> date | None:
    value = value.strip().rstrip('.')
    if value.lower() in {'present', 'current', 'ongoing', ''}:
        return None
    if re.fullmatch(r'\d{4}', value):
        return date(int(value), 1, 1)
    if re.fullmatch(r'\d{4}-\d{2}', value):
        try:
            return date.fromisoformat(value + '-01')
        except ValueError:
            return None
    match = re.fullmatch(r'([A-Za-z]+)\.?\s+(\d{4})', value)
    if match:
        month = MONTHS.get(match.group(1)[:3].lower())
        if month:
            return date(int(match.group(2)), month, 1)
    return None


def _sections(text: str) -> dict[str, list[str]]:
    sections = {'experience': [], 'education': []}
    active = None
    for raw in text.splitlines():
        line = raw.strip()
        heading = re.sub(r'\s+', ' ', line).upper().rstrip(':')
        if heading in HEADINGS:
            active = HEADINGS[heading]
            continue
        if heading in STOP_HEADINGS:
            active = None
            continue
        if active and line and not re.search(r'Curriculum Vitae\s+Page\s+\d+', line, re.I):
            sections[active].append(line)
    return sections


def _labeled(lines: list[str], kind: str) -> list[dict]:
    records = []
    record = {}
    for line in lines:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip().lower()
        if key not in FIELDS[kind]:
            continue
        if key in record:
            records.append(record)
            record = {}
        record[key] = value.strip()
    if record:
        records.append(record)
    return records


def _dated_line(line: str):
    match = RANGE_RE.search(line)
    if not match:
        return None
    return line[:match.start()].strip(' ,\t'), match.group('start'), match.group('end')


def extract_experiences(text: str) -> list[ResumeExperience]:
    lines = _sections(text)['experience']
    results = []
    for record in _labeled(lines, 'experience'):
        if record.get('job title') or record.get('company'):
            results.append(ResumeExperience(company_name=record.get('company'), job_title=record.get('job title'),
                start_date=parse_month(record.get('start', '')), end_date=parse_month(record.get('end', ''))))
    if results:
        return results
    for line in lines:
        dated = _dated_line(line)
        if not dated:
            continue
        title, start, end = dated
        match = EXP_RE.match(title)
        if match and match.group('company').strip() and match.group('role').strip():
            results.append(ResumeExperience(company_name=match.group('company').strip(),
                job_title=match.group('role').strip(), start_date=parse_month(start), end_date=parse_month(end)))
    return results


def extract_educations(text: str) -> list[ResumeEducation]:
    lines = _sections(text)['education']
    results = []
    for record in _labeled(lines, 'education'):
        if record.get('institution') or record.get('degree'):
            results.append(ResumeEducation(institution=record.get('institution'), degree=record.get('degree'),
                start_date=parse_month(record.get('start', '')), end_date=parse_month(record.get('end', ''))))
    if results:
        return results
    for index, line in enumerate(lines):
        dated = _dated_line(line)
        if not dated:
            continue
        degree, start, end = dated
        if not DEGREE_RE.match(degree):
            continue
        institution = lines[index + 1] if index + 1 < len(lines) and not _dated_line(lines[index + 1]) else None
        results.append(ResumeEducation(institution=institution, degree=degree,
            start_date=parse_month(start), end_date=parse_month(end)))
    return results
