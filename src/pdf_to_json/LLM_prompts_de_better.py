import json

JSON_EXAMPLE = {
    "title": "[Extracted Form Title]",
    "help_text": "[Short Program Description]",
    "Instructions": "[Detailed Program Instructions]",
    "sections": [
        {
            "title": "[Section Name]",
            "help_text": "[Relevant Instructional or informational Text]",
            "fields": [
                {"label": "[Field Label]", "type": "[text|number|date|email|phone|currency|address|name]", "help_text": "[Instruction]", "id": "[unique_snake_case_id]"},
                {"label": "[Field Label]", "type": "radio_button", "options": ["opt 1", "opt 2"], "help_text": "[Instruction]", "id": "[unique_snake_case_id]"},
                {"label": "[Field Label]", "type": "checkbox", "options": ["opt 1", "opt 2"], "help_text": "[Instruction]", "id": "[unique_snake_case_id]"}
            ]
        },
        {
            "title": "[Repeating Section Name (e.g., Children, Vehicles)]",
            "help_text": "[Instruction]",
            "type": "repeating_section",
            "entity_nickname": "[Singular noun for the entity, e.g., 'Kind']",
            "fields": [
                {"label": "[Field Label]", "type": "text", "help_text": "[Instruction]", "id": "[unique_snake_case_id]"}
            ]
        },
        {
            "title": "[Section Name]",
            "fields": [
                {"label": "[Field Label]", "type": "fileupload", "help_text": "[Instruction]", "id": "[unique_snake_case_id]"}
            ]
        }
    ]
}

class LLMPrompts:
    @staticmethod
    def pdf_to_json_prompt():
        """Prompt for converting PDF text to intermediary JSON, optimized for both Side-by-Side entities and Attachments."""
        prompt = f"""
        You are an expert in document analysis and structured form modeling for German government bureaucracy.
        
        **INPUT:**
        You will receive text extracted from a German PDF form (with `` tags).
        
        **OUTPUT:**
        Generate valid JSON representing the form structure, strictly following this schema:
        {json.dumps(JSON_EXAMPLE, indent=4)}

        **CRITICAL EXTRACTION LOGIC (The "Hybrid" Approach):**

        1. **Handling Parallel Columns (The "Basicinc" Rule):**
           - If the form lists two distinct entities side-by-side (e.g., "Antragsteller" on Left, "Person 2" on Right), **DO NOT mix their fields**.
           - **Action:** Create **SEPARATE Sections** for them. 
             - Correct: Section "I. Antragsteller" (containing Name, Birthdate) -> Section "II. Partner/Person 2" (containing Name, Birthdate).
             - Incorrect: Section "Personal Data" (containing Name-Applicant, Name-Partner, Birthdate-Applicant, Birthdate-Partner).
           - Maintain the distinction clearly.

        2. **Handling Attachments (The "Parking" Rule):**
           - Scan the ENTIRE document for required documents (often listed as "Anlagen", "Beizufügen", "Nachweise").
           - **Action:** Create a dedicated **Section** at the end called "Erforderliche Nachweise" (Required Documents).
           - Populate this section with `fileupload` fields for each document mentioned (e.g., "Kopie Fahrzeugschein", "Personalausweis").

        3. **Section Logic:**
           - Use `repeating_section` for lists of items that can be infinite (Children, Vehicles, Previous Addresses).
           - Use standard `sections` for fixed entities (Applicant, Partner).
        
        4. **Field Types & German Context:**
           - **Radio vs Checkbox:** If text says "nur eine Antwort" or "bitte ankreuzen" (singular), use `radio_button`. If multiple allow, use `checkbox`.
           - **Privacy:** EXTRACT sensitive fields (Rentenversicherungsnummer, etc.). Do not skip them.
           - **Data Types:** Detect `currency` (Euro/Betrag), `date` (Datum), `phone` (Telefon), `email`.

        **RULES:**
        - Keep ALL Labels, Titles, and Help Text in **German**.
        - Generate unique `snake_case` IDs.
        - Output ONLY valid JSON.
        """
        return prompt

    @staticmethod
    def fix_malformed_json_prompt(text):
        """Prompt for repair of malformed JSON."""
        prompt = f"""
        You are a JSON repair engine. The following text contains a JSON object representing a government form, but it may be truncated or syntactically incorrect:
        {text}
        **Your Task:**
        1. Fix any missing brackets `}}` or `]`.
        2. Ensure all keys and string values are properly escaped and closed.
        3. Do NOT change the content (German text) or the structure logic.
        Return ONLY the corrected, valid JSON string.
        """
        return prompt

    @staticmethod
    def post_process_json_prompt(text):
        """Post-processes extracted German JSON to collate fields correctly."""
        prompt = f"""
        You are a Data Architect for Civiform. Process the following raw JSON extracted from a German form to make it user-friendly:
        
        {text}
        
        **Processing Rules:**
        
        1. **Preserve Entity Grouping (Fixes "Basicinc" issue):**
           - Do **NOT** flatten distinct sections for different people into one mess. 
           - If the input correctly separated "Antragsteller" and "Person 2" into different sections, **KEEP them separate**.
           - Ensure titles distinguish them (e.g., "Persönliche Daten (Antragsteller)" vs "Persönliche Daten (Person 2)").

        2. **Consolidate Uploads (Fixes "Parking" issue):**
           - If there are `fileupload` or text fields asking for "Nachweise" scattered across the form, MOVE them all to a final single section called "Nachweise".

        3. **Collation (Merging Fields):**
           - **Names:** Merge "Vorname", "Nachname" into a single `name` field.
           - **Addresses:** Merge "Straße", "Nr", "PLZ", "Ort" into a single `address` field.
           - *Constraint:* NEVER merge fields from different Sections (e.g. do not merge Applicant's address with Partner's address).

        4. **Refine Data Types:**
           - Money -> `currency`
           - Dates -> `date`
           - Phone -> `phone`
           - Email -> `email`

        5. **Validations:**
           - `radio_button` must have 2+ options.
           - `checkbox` must have 1+ options.
           - `repeating_section` must have `entity_nickname`.

        **Output:**
        Return the cleaned, validated JSON following this schema:
        {json.dumps(JSON_EXAMPLE, indent=4)}
        
        Return ONLY JSON.
        """
        return prompt