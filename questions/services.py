import re
import PyPDF2

def extract_questions_from_pdf(file_obj):
    """Reads a PDF file from memory and extracts text to parse questions."""
    reader = PyPDF2.PdfReader(file_obj)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
            
    return parse_questions_from_text(text)

def parse_questions_from_text(text):
    """
    Simulates AI extraction using smart regex heuristics.
    Looks for question numbers (1. or Q1.) and explicit Answer prefixes.
    """
    lines = text.split('\n')
    questions = []
    
    current_q = None
    
    # Matches "1. ", "1) ", "Q1. ", "Q1: ", "Question 1: "
    q_start_pattern = re.compile(r'^(?:Q(?:uestion)?\s*\d+|[0-9]+)[\.\)\:]\s+(.*)', re.IGNORECASE)
    # Matches "Answer:", "Ans:", "A."
    ans_start_pattern = re.compile(r'^(?:A(?:nswer|ns)?\s*[\.\:\)])\s*(.*)', re.IGNORECASE)
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        q_match = q_start_pattern.match(line_clean)
        if q_match:
            if current_q:
                questions.append(current_q)
            current_q = {'text': line_clean, 'answer': ''}
            continue
            
        a_match = ans_start_pattern.match(line_clean)
        if a_match and current_q:
            current_q['answer'] += line_clean + "\n"
            continue
            
        if current_q:
            # If we've started collecting the answer, append to answer. Otherwise, append to question.
            if current_q['answer'] or "answer" in line_clean.lower():
                current_q['answer'] += line_clean + "\n"
            else:
                current_q['text'] += "\n" + line_clean
                
    if current_q:
        questions.append(current_q)
        
    # Fallback heuristic: If no numbered questions were found, look for sentences ending in '?'
    if not questions:
        paragraphs = re.split(r'\n\s*\n', text)
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if '?' in p:
                # Split at the first question mark
                parts = p.split('?', 1)
                q_text = parts[0].strip() + '?'
                ans_text = parts[1].strip()
                questions.append({'text': q_text, 'answer': ans_text})
                
    # Clean up formatting
    for q in questions:
        q['text'] = q['text'].strip()
        q['answer'] = q['answer'].strip()
        
    return questions
