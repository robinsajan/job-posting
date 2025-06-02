from flask import Flask, render_template, request, redirect, send_file
import io
import pandas as pd
import os
from dotenv import load_dotenv
import PIL
import google.generativeai as genai
from datetime import datetime

load_dotenv() 

app = Flask(__name__)

# Store items in a simple in-memory list (will reset on app restart)
items = []

API_KEY=os.getenv("API_KEY")

GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

def llm(query):
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(query)
    return response.text


def vllm(query,image):
    model=genai.GenerativeModel('gemini-2.0-flash')
    response=model.generate_content([query,image])
    return response.text
  
def call_vllm(image):
    prompt="""

You are a specialized job information extraction assistant trained to extract structured job data from images. Your task is to read all visible text in the image and return a deduplicated Python list of job roles.

## Core Requirements

- **Read ALL visible text** - scan the entire image thoroughly
- **Return each job only once** - eliminate duplicates across different formats
- **Output raw Python code only** - no explanations, markdown, or commentary
- **Extract only explicit information** - never infer or assume missing details

## Critical Deduplication Rules

1. **Same job, different formats** - If a job appears in both paragraph and bullet format, return only one entry
2. **Similar titles, different companies** - These are separate jobs, include both
3. **Identical descriptions** - Merge into single entry with combined details
4. **Multiple locations for same role** - Combine locations or create separate entries based on context

## Required Output Format

```python
[
    {
        "job_title": "",
        "company": "",  # Only if mentioned outside the email
        "location": "",
        "salary": "",
        "requirements": [],
        "point_of_contact": []
    }
]
```

## Field Extraction Guidelines

### job_title
- Extract exact title as displayed
- Include seniority/level indicators (Senior, Junior, Lead, Manager)
- Preserve technical specifications (Full Stack, Frontend, Backend)

### company
- **ONLY extract if explicitly mentioned outside email addresses**
- Do not derive company names from email domains or signatures
- Include if mentioned in headers, footers, or job descriptions

### location
- Extract all location formats: city, state, country, "Remote", "Hybrid"
- Include multiple locations if specified for single role
- Preserve location qualifiers ("Flexible", "Occasional travel")

### salary
- Include full compensation details as stated
- Preserve currency symbols, ranges, time periods
- Include equity, bonuses, or other compensation if mentioned

### requirements
- Return as list of strings
- Include technical skills, experience levels, education requirements
- Extract from bullet points, paragraphs, or qualification sections
- Separate each distinct requirement

## Image Processing Instructions

1. **Scan entire image** - Read all visible text from top to bottom, left to right
2. **Parse all text formats** - Headers, paragraphs, bullet points, tables, captions
3. **Identify job sections** - Look for job listings, descriptions, requirements
4. **Extract contact information** - Names, emails, phone numbers anywhere in image
5. **Check for duplicates** - Same job in different formats should be merged

## Deduplication Process

Before returning results:
- Compare job titles and descriptions for duplicates
- Merge identical jobs from different sections
- Combine scattered information for same role
- Ensure each unique job appears only once
- Verify all visible text has been processed

## Quality Assurance

- Each job has its own dictionary entry
- No company names inferred from email domains
- All explicitly visible information captured
- Lists used for multi-value fields (requirements, contacts)
- Empty strings ("") for missing information
- Valid Python list syntax"""
    response=vllm(prompt,image)
    response=response.replace("```python","").replace("```","")
    response=eval(response)

    return response
  
def call_llm(input):
    prompt="""You are an expert-level job information extractor. Extract job-related information from unstructured text and return it as a Python list of dictionaries.
Core Instructions

Extract only explicitly mentioned information - never infer or guess
One dictionary per distinct job role - separate even if listed together
Use empty strings ("") for missing fields - no null values or assumptions
Return raw Python code only - no markdown, explanations, or commentary

Required Output Format
python[
    {
        "job_title": "",
        "company": "",
        "location": "",
        "salary": "",
        "requirements": [],
        "point_of_contact": []
    }
]
Field Extraction Rules
job_title

Extract exact title as stated
If multiple titles listed separately, create separate entries
Include seniority levels if mentioned (Senior, Junior, Lead, etc.)

company

Only extract if company name is explicitly stated in the text
DO NOT derive company names from email domains
Must be mentioned outside of email addresses

location

Extract specific locations (city, state, country)
Include "Remote" if mentioned
If one location applies to multiple roles, include it for each

salary

Include full salary information as stated
Preserve currency, ranges, and time periods (hourly/monthly/yearly)
Include benefits if mentioned with salary

requirements

Return as list of strings
Include technical skills, experience levels, education
Separate each distinct requirement
Include both required and preferred qualifications

point_of_contact

Include names, email addresses, phone numbers
Each contact detail as separate list item
Preserve formatting of contact information

Special Cases

Multiple roles in one listing: Create separate dictionary entries
Shared information: Repeat common details (like location) for each role
Incomplete postings: Fill available fields, leave others empty
Contact information: Always include if present, regardless of format

Quality Checks
Before returning results, verify:

 Each job has its own dictionary
 No inferred company names from email domains
 All explicitly mentioned information captured
 Lists used for multi-value fields
 No commentary or explanations included
 Valid Python list syntax

Use this unstructured input:
"""
    prompt=prompt+input
    output=llm(prompt)
    output=output.replace("```python", "").replace("```", "").strip()
    output=eval(output)
    return output

def generate_excel():
    global items
    print("called")
    df = pd.DataFrame([
        {
            "Sr. No.": idx + 1,
            "Job Title": job.get("job_title", ""),
            "Company Name": job.get("company", ""),
            "Location(s)": job.get("location", ""),
            "CV to be sent at":"; ".join(job.get("point_of_contact", [])),
            "Requirements": "; ".join(job.get("requirements", []))
            
        }
        for idx, job in enumerate(items)
    ])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = "jobs"+str(timestamp)+".csv"
    df.to_csv(file_path, index=False)

    # Send the file to client
    return send_file(
        file_path,
        mimetype='text/csv',
        as_attachment=True,
        download_name=file_path
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
            return generate_excel()

    return render_template("index.html", items=items)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
