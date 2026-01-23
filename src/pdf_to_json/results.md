# Comprehensive Comparison: PDF to JSON Conversion Strategies

This report provides a detailed three-way comparison of the conversion results using **`LLM_prompts` (Default)**, **`LLM_prompts_de`**, and **`LLM_prompts_de_better`** prompts for the Resident Parking and Basic Income forms.

---

## 🅿️ Resident Parking (Residents' Parking Permit)

*Goal: Simple transactional form with address and vehicle metadata.*

| Feature | `LLM_prompts` (Default) | `LLM_prompts_de` | `LLM_prompts_de_better` |
| :--- | :--- | :--- | :--- |
| **Logic** | Literal PDF copy. Flat structure. | Structural optimization. Semantic sections. | **High-detail extraction.** Metadata consolidated. |
| **Field Types** | Mostly `text` and `radio_button`. | Uses `address` and `name` types. | **Granular `fileupload`** and `address`. |
| **Instructions** | Large blocks of text. | Summarized in `help_text`. | **Metadata-focused** instructions. |
| **Attachments** | Not explicitly extracted. | Single `fileupload` field. | **Granular upload fields** per document type. |

### Verdict (Parking permit)

**Winner: `LLM_prompts_de_better`**
The "Better" prompt transforms the form into a truly digital-first experience by splitting the generic "Attachments" instruction into specific upload fields (`nachweis_fahrzeugschein`, `nachweis_personaldokument`, etc.), which is critical for user guidance.

---

## 🏠 Basic Income

*Goal: Highly complex social benefits form (~300 fields) with multiple entities (Person 1, Person 2).*

| Feature | Standard (Default) | `LLM_prompts_de` | `LLM_prompts_de_better` |
| :--- | :--- | :--- | :--- |
| **Structure** | Unmanageable flat list of 300+ fields. | **Nested JSON Groups** (p1/p2). | Flat list with prefixed IDs (`p1_...`). |
| **Organization** | No logical grouping. | Clear sub-structuring by person/topic. | Topics grouped by title; IDs are flat. |
| **Readability** | Poor (literal transcription). | **Excellent (dev-friendly hierarchy).** | Good (better field labels). |
| **Attachments** | Hidden in instruction text. | Basic detection of attachments. | **Full extraction of 15+ individual file fields.** |

### Verdict (Basic Income)

**Winner: Tie (Custom vs. `LLM_prompts_de_better`)**

- **Use `LLM_prompts_de`** if your application logic requires nested objects (e.g., `applicant.name`, `partner.name`).
- **Use `LLM_prompts_de_better`** if you need the most granular automated extraction of the 15+ sub-documents (Anlagen) required for social benefits.

---

## 🏁 Summary of Strategic Differences

### 1. `LLM_prompts` (default)

- **Pros**: Quickest literal copy of the paper form.
- **Cons**: High manual cleanup required. No semantic typing. No document extraction.

### 2. `LLM_prompts_de`

- **Pros**: **Best for structural integrity.** Introduces nesting (Groups) which mirrors the logical relationship of the form data (e.g., separating Applicant from Partner data objects).
- **Cons**: Can sometimes miss fine-grained metadata details in the headers/instructions.

### 3. `LLM_prompts_de_better`

- **Pros**: **Best for feature-rich conversion.** Aggressively identifies metadata, consolidates specific "Change" scenarios, and provides the most granular attachment handling.
- **Cons**: Favors a flat ID structure over nested groups, which may be less convenient for complex entity models.

---

## 🚀 Final Recommendation Decision Guide

| If you need... | Then use... |
| :--- | :--- |
| A quick digital draft for a simple form | **`LLM_prompts`** |
| Deeply nested data structures for multi-person forms | **`LLM_prompts_de`** |
| **A production-ready digital form with clear file upload logic** | **`LLM_prompts_de_better`** |
