from flask import Flask, render_template, request, redirect, send_file
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from together import Together
import os
from dotenv import load_dotenv

load_dotenv() 

app = Flask(__name__)

# Store items in a simple in-memory list (will reset on app restart)
items = []

API_KEY=os.getenv("API_KEY")

client = Together(api_key=API_KEY)

def llm(query):
  response = client.chat.completions.create(
      model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
      messages=[{"role": "user", "content": query}],
  )
  return response.choices[0].message.content

def call_llm(input):
    prompt=f"""You are an expert-level job information extractor. From the unstructured text provided, extract and return a Python list where each item is a dictionary containing job-related fields.

Only extract fields explicitly mentioned in the text.
✅ Do not infer company names from email domains.
✅ Do not output any commentary, explanation, or markdown.
✅ Do not guess values — leave them as empty string "" if not found.

Required Output Format (Python only):

python
Copy
Edit
[
    {{
        "job_title": "",
        "company": "",  # Only if mentioned outside the email
        "location": "",
        "salary": "",
        "summary": "",  # A 2-sentence summary based on any text available
        "employment_type": "",
        "requirements": [],
        "point_of_contact": "",
        "benefits": [],
        "how_to_apply": "",
        "posting_date": "",
        "deadline": ""
    }}
]
Populate as many fields as possible for each role. For fields like "requirements", "benefits", and "point_of_contact", return lists or strings as appropriate. Use clear logic to form a 2-sentence summary if any descriptive text is provided.

Special Instructions:

Extract company name only if clearly stated outside the email domain.

Group roles individually even if listed in a single line (e.g., items in a numbered list).

The location “Mumbai” should be included if mentioned as common to all roles.

Both names and emails should be included in "point_of_contact" if available.

Use this unstructured text:
{input}"""
    return llm(prompt)

@app.route("/", methods=["GET", "POST"])
def index():
    global items
    if request.method == "POST":
        if 'add' in request.form:
            text = request.form.get("item")
            if text:
                text=call_llm(text)
                items.append(text)
        elif 'generate' in request.form:
            return generate_pdf()
    return render_template("index.html", items=items)

def generate_pdf():
    doc = SimpleDocTemplate("jobs.pdf", pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Sample job data
    jobs = items

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle('normal', fontName='Helvetica', fontSize=9, leading=11)
    bold_style = ParagraphStyle(
        name='BoldStyle',
        fontName='Helvetica-Bold',  # <-- This makes the text bold
        fontSize=10,
        leading=12
    )

    def job_to_table(job):
        data = []
        if job['job_title']: data.append(['Job Title', Paragraph(job['job_title'], bold_style)])
        if job['company']: data.append(['Company', Paragraph(job['company'], normal_style)])
        if job['location']: data.append(['Location', Paragraph(job['location'], normal_style)])
        if job['salary']: data.append(['Salary', Paragraph(job['salary'], normal_style)])
        if job['summary']: data.append(['Summary', Paragraph(job['summary'], normal_style)])
        if job['employment_type']: data.append(['Employment Type', Paragraph(job['employment_type'], normal_style)])
        if job['requirements']: data.append(['Requirements', Paragraph('; '.join(job['requirements']), normal_style)])
        if job['how_to_apply']: data.append(['How to Apply', Paragraph(job['how_to_apply'], normal_style)])
        if job['point_of_contact']: data.append(['Contact', Paragraph(job['point_of_contact'], normal_style)])

        table = Table(data, colWidths=[80, 400])  # Adjusted column width to fit within page
        table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.75, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        return table

    # Build the PDF
    elements = []
    for job in jobs:
        elements.append(job_to_table(job))
        elements.append(Spacer(1, 12))

    doc.build(elements)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
