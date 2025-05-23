from flask import Flask, render_template, request, redirect, send_file
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from together import Together
import os
from dotenv import load_dotenv
import PIL
import google.generativeai as genai

load_dotenv() 

app = Flask(__name__)

# Store items in a simple in-memory list (will reset on app restart)
items = []

API_KEY=os.getenv("API_KEY")
client = Together(api_key=API_KEY)

GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

def llm(query):
  response = client.chat.completions.create(
      model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
      messages=[{"role": "user", "content": query}],
  )
  return response.choices[0].message.content

def vllm(query,image):
    model=genai.GenerativeModel('gemini-2.0-flash')
    response=model.generate_content([query,image])
    return response.text
  
def call_vllm(image):
    prompt="""You are a specialized job information extraction assistant trained to extract structured job data from images. Your task is to read the full content of the image (including all visible text) and return a deduplicated Python list of job roles.

Important Instructions:

✅ Return each job only once, even if it appears multiple times in the image (e.g., in both paragraph and bullet format).

❌ Do not repeat job entries under any condition.

✅ Do not infer company names from email addresses — use only explicitly stated company names.

✅ Do not include any explanation, markdown, or formatting — return only the Python list.

Output Format (Python list only):

python
Copy
Edit
[
    {
        "job_title": "",
        "company": "",  # Only if clearly mentioned outside emails
        "location": "",
        "salary": "",
        "summary": "",  # Condense any job description into 2 sentences
        "employment_type": "",
        "requirements": [],
        "point_of_contact": [],
        "benefits": [],
        "how_to_apply": "",
        "posting_date": "",
        "deadline": ""
    }
]
Instructions for Field Handling:

Parse all visible text from the image.

Treat numbered or bulleted job lists as separate entries, but check for duplicate descriptions/titles and return only unique jobs.

Use bullet points or surrounding text to populate requirements, benefits, or summary where possible.

Combine duplicate details (e.g., two lines describing the same job) into a single entry.

Leave missing values as empty strings ""
"""
    response=vllm(prompt,image)
    response=response.replace("```python","").replace("```","")
    response=eval(response)

    return response
  
def call_llm(input):
    prompt=f"""You are an expert-level job information extractor. From the unstructured text provided, extract and return a Python list where each item is a dictionary containing job-related fields.

Only extract fields explicitly mentioned in the text.
✅ Do not infer company names from email domains.
✅ Do not output any commentary, explanation, or markdown.
✅ Do not guess values — leave them as empty string "" if not found.

Required Output Format (Python only):

[
    {{
        "job_title": "",
        "company": "",  # Only if mentioned outside the email
        "location": "",
        "salary": "",
        "summary": "",  # A 2-sentence summary based on any text available
        "employment_type": "",
        "requirements": [],
        "point_of_contact": [],
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
    output=llm(prompt)
    output=eval(output)
    return output

def generate_pdf():
    global items
    print("called")

    # Use BytesIO for in-memory PDF
    pdf_buffer = io.BytesIO()
    
    # Build doc using in-memory buffer
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )

    jobs = items

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle('normal', fontName='Helvetica', fontSize=9, leading=11)
    bold_style = ParagraphStyle(
        name='BoldStyle',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12
    )

    def job_to_table(job):
        data = []
        if job.get('job_title'): data.append(['Job Title', Paragraph(job['job_title'], bold_style)])
        if job.get('company'): data.append(['Company', Paragraph(job['company'], normal_style)])
        if job.get('location'): data.append(['Location', Paragraph(job['location'], normal_style)])
        if job.get('salary'): data.append(['Salary', Paragraph(job['salary'], normal_style)])
        if job.get('summary'): data.append(['Summary', Paragraph(job['summary'], normal_style)])
        if job.get('employment_type'): data.append(['Employment Type', Paragraph(job['employment_type'], normal_style)])
        if job.get('requirements'): data.append(['Requirements', Paragraph('; '.join(job['requirements']), normal_style)])
        if job.get('how_to_apply'): data.append(['How to Apply', Paragraph(job['how_to_apply'], normal_style)])
        if job['point_of_contact']: data.append(['Contact', Paragraph('; '.join(job['point_of_contact']), normal_style)])

        table = Table(data, colWidths=[80, 400])
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

    elements = []
    for job in jobs:
        elements.append(job_to_table(job))
        elements.append(Spacer(1, 12))

    doc.build(elements)  # Write to pdf_buffer
    pdf_buffer.seek(0)   # Rewind the buffer

    # Optionally clear jobs
    items = []

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="jobs.pdf",
        mimetype="application/pdf"
    )
@app.route("/", methods=["GET", "POST"])
def index():
    global items
    if request.method == "POST":
        if 'add' in request.form:
            text = request.form.get("item", "").strip()
            image = request.files.get("image")

            if image and image.filename != "":
                image=PIL.Image.open(image.stream)
                text=call_vllm(image)
                items+=text

            if text:
                text = call_llm(text)
                items+=text
        elif 'remove' in request.form:
          if items:
              items=[]
            
        elif 'generate' in request.form:
            return generate_pdf()

    return render_template("index.html", items=items)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
