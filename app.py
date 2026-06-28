import os
import re
from flask import Flask, request, render_template, send_from_directory, redirect, flash
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from docx import Document
from fpdf import FPDF

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
DICTIONARY_FILE = os.path.join(OUTPUT_FOLDER, "custom_dictionary.txt")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ---------------- FUNCTIONS ----------------
def clean_ocr_text_pro(text):
    """
    Advanced OCR text cleanup:
    - Fix OCR errors and misspellings
    - Remove stray symbols and numbers
    - Merge broken lines
    - Add headings and paragraphs for Java features
    """
    # Common OCR corrections
    corrections = {
        r"\bTava\b": "Java",
        r"\bJov(e|a)\b": "Java",
        r"\bbyl[e|t]code\b": "bytecode",
        r"\bCrtand\b": "C and C",
        r"\bDynamia\b": "Dynamic",
        r"\braanage\b": "management",
        r"\bfealure\b": "features",
        r"\bprgrams\b": "programs",
        r"\bmult[- ]?tipletasks\b": "multiple tasks",
        r"\b4o\b": "to",
        r"\b4i\b": "to",
        r"\bTls\b": "is",
        r"\bwun\b": "run",
        r"\banguhere\b": "anywhere",
        r"\bShong ty\b": "strong type",
        r"\bfears Lee\b": "ensures",
        r"[{}~+|_—]+": "",  # remove stray symbols
        r"\s{2,}": " ",      # multiple spaces -> single space
    }
    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Remove stray numbers
    text = re.sub(r"\b\d+\b", "", text)

    # Merge broken lines
    lines = text.split("\n")
    merged = []
    buffer = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if buffer:
            if not buffer.endswith((".", "!", "?", ":")):
                buffer += " " + line
            else:
                merged.append(buffer)
                buffer = line
        else:
            buffer = line
    if buffer:
        merged.append(buffer)

    cleaned_text = " ".join(merged)

    # Add headings
    headings = {
        r"Platform Independence": "**Platform Independence:**",
        r"Object Oriented": "**Object-Oriented:**",
        r"Robust and Secure": "**Robust and Secure:**",
        r"Dynamic": "**Dynamic:**",
        r"High Performance": "**High Performance:**",
        r"Distributed": "**Distributed:**",
        r"Portable": "**Portable:**",
        r"Rich Standard Library": "**Rich Standard Library:**"
    }
    for pattern, replacement in headings.items():
        cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=re.IGNORECASE)

    # Split into paragraphs after headings
    final_text = re.sub(r"(\*\*.*?:\*\*)", r"\n\1\n", cleaned_text)
    final_text = "\n".join(line.strip() for line in final_text.splitlines() if line.strip())

    return final_text


def save_as_pdf(text, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in text.split("\n"):
        safe_line = "".join(char if ord(char) < 256 else "?" for char in line)
        pdf.multi_cell(0, 8, safe_line)
    pdf.output(output_path)


def add_words_to_dictionary(words):
    with open(DICTIONARY_FILE, "a", encoding="utf-8") as f:
        for word in words:
            f.write(word.strip() + "\n")


# ---------------- ROUTES ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    words_added = []
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            flash("Please upload a file!")
            return redirect("/")

        file = request.files["file"]
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # OCR extraction
        extracted_text = ""
        try:
            if filename.lower().endswith(".pdf"):
                pages = convert_from_path(filepath)
                for page in pages:
                    extracted_text += pytesseract.image_to_string(page) + "\n"
            else:
                img = Image.open(filepath)
                extracted_text = pytesseract.image_to_string(img)
        except Exception as e:
            flash(f"OCR error: {e}")
            return redirect("/")

        # Clean OCR text
        formatted_text = clean_ocr_text_pro(extracted_text)

        # Save TXT
        txt_path = os.path.join(OUTPUT_FOLDER, "output.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(formatted_text)

        # Save DOCX
        docx_path = os.path.join(OUTPUT_FOLDER, "output.docx")
        doc = Document()
        doc.add_paragraph(formatted_text)
        doc.save(docx_path)

        # Save PDF
        pdf_path = os.path.join(OUTPUT_FOLDER, "output.pdf")
        try:
            save_as_pdf(formatted_text, pdf_path)
        except Exception as e:
            flash(f"PDF generation error: {e}")
            pdf_path = None

        # Add words to dictionary
        word_list = request.form.get("dictionary_words")
        if word_list:
            words = [w for w in word_list.split(",") if w.strip()]
            add_words_to_dictionary(words)
            words_added = words

        return render_template(
            "index.html",
            success=True,
            raw_text=extracted_text,
            cleaned_text=formatted_text,
            txt_url="/download/output.txt",
            docx_url="/download/output.docx",
            pdf_url="/download/output.pdf",
            words_added=words_added
        )

    return render_template("index.html", success=False)


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


@app.route("/download-dictionary")
def download_dictionary():
    if os.path.exists(DICTIONARY_FILE):
        return send_from_directory(OUTPUT_FOLDER, "custom_dictionary.txt", as_attachment=True)
    else:
        flash("Dictionary file not found!")
        return redirect("/")


@app.route("/clear-dictionary", methods=["POST"])
def clear_dictionary():
    if os.path.exists(DICTIONARY_FILE):
        os.remove(DICTIONARY_FILE)
        flash("Dictionary cleared!")
    else:
        flash("No dictionary file to clear!")
    return redirect("/")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    app.run(debug=True)
