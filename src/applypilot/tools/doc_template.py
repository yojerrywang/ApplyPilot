"""Google Doc template rendering for tailored resumes.

Takes a tailored resume text file and fills placeholders in a Google Doc template.
Then exports a PDF for review/edit workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from applypilot.google.drive import copy_file, replace_text_in_google_doc, export_google_doc_as_pdf


@dataclass
class ResumeParts:
    name: str
    title: str
    contact: str
    phone: str
    email: str
    summary: str
    skills: str
    experience: str
    projects: str
    service: str
    education: str


def _slice_section(lines: list[str], section: str, all_sections: set[str]) -> str:
    """Extract section body by heading (uppercase headings used by tailoring output)."""
    try:
        start = lines.index(section)
    except ValueError:
        return ""

    out: list[str] = []
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if line in all_sections:
            break
        out.append(line)
        i += 1
    return "\n".join(out).strip()


def parse_tailored_resume_text(path: Path) -> ResumeParts:
    """Parse ApplyPilot tailored .txt into structured sections for template fill."""
    raw_lines = [ln.rstrip() for ln in path.read_text(encoding="utf-8").splitlines()]
    lines = [ln for ln in raw_lines]

    name = lines[0].strip() if len(lines) > 0 else ""
    title = lines[1].strip() if len(lines) > 1 else ""
    contact = lines[2].strip() if len(lines) > 2 else ""

    sections = {"SUMMARY", "TECHNICAL SKILLS", "EXPERIENCE", "PROJECTS", "EDUCATION", "SERVICE"}

    summary = _slice_section(lines, "SUMMARY", sections)
    skills = _slice_section(lines, "TECHNICAL SKILLS", sections)
    experience = _slice_section(lines, "EXPERIENCE", sections)
    projects = _slice_section(lines, "PROJECTS", sections)
    service = _slice_section(lines, "SERVICE", sections)
    education = _slice_section(lines, "EDUCATION", sections)

    # Contact line is typically "email | phone | links"
    email = ""
    phone = ""
    for part in [p.strip() for p in contact.split("|")]:
        if "@" in part and not email:
            email = part
        if any(ch.isdigit() for ch in part) and not phone:
            phone = part

    return ResumeParts(
        name=name,
        title=title,
        contact=contact,
        phone=phone,
        email=email,
        summary=summary,
        skills=skills,
        experience=experience,
        projects=projects,
        service=service,
        education=education,
    )


def build_replacements(parts: ResumeParts) -> dict[str, str]:
    """Build placeholder mapping expected in the Google Doc template."""
    return {
        "{{NAME}}": parts.name,
        "{{TITLE}}": parts.title,
        "{{CONTACT}}": parts.contact,
        "{{PHONE}}": parts.phone,
        "{{EMAIL}}": parts.email,
        "{{SUMMARY}}": parts.summary,
        "{{SKILLS}}": parts.skills,
        "{{EXPERIENCE}}": parts.experience,
        "{{PROJECTS}}": parts.projects,
        "{{SERVICE}}": parts.service,
        "{{EDUCATION}}": parts.education,
    }


def render_template_to_doc_and_pdf(
    *,
    template_doc_id: str,
    tailored_txt_path: Path,
    output_doc_name: str,
    output_pdf_path: Path,
    drive_folder_id: str | None = None,
) -> tuple[str, Path]:
    """Copy template doc, fill placeholders, and export PDF.

    Returns:
        (new_document_id, output_pdf_path)
    """
    parts = parse_tailored_resume_text(tailored_txt_path)
    replacements = build_replacements(parts)

    new_doc_id = copy_file(template_doc_id, new_name=output_doc_name, folder_id=drive_folder_id)
    replace_text_in_google_doc(new_doc_id, replacements)
    pdf_path = export_google_doc_as_pdf(new_doc_id, output_pdf_path)
    return new_doc_id, pdf_path
