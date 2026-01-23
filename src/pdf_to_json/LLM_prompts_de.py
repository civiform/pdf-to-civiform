import json

JSON_EXAMPLE = {
    "title": "[Extracted Form Title]",
    "help_text": "[Short Program Description]",
    "Instructions": "[Detailed Program Instructions]",
    "sections": [
        {
            "title": "[Section Name]",
            "help_text": "[Relevant Instructional or informational Text (can be enclosed in brackets)]",
            "fields": [
                {"label": "[Field Label]", "type": "[Field Type]", "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"},
                {"label": "[Field Label]", "type": "[radio_button]", "options": ["opt 1", "opt 2", "opt 3"], "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"},
                {"label": "[Field Label]", "type": "[checkbox]", "options": ["opt 1", "opt 2", "opt 3"], "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"}
            ]
        },
        {
            "title": "[Section Name]",
            "help_text": "[Relevant Instructional or informational Text (can be enclosed in brackets)]",
            "type": "repeating_section",
            "fields": [
                {"label": "[Field Label]", "type": "[Field Type]", "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"},
                {"label": "[Field Label]", "type": "[radio_button]", "options": ["opt 1", "opt 2", "opt 3"], "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"},
                {"label": "[Field Label]", "type": "[checkbox]", "options": ["opt 1", "opt 2", "opt 3"], "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"}
            ]
        },
        {
            "title": "[Section Name]",
            "help_text": "[Relevant Instructional or informational Text (can be enclosed in brackets)]",
            "fields": [
                {"label": "[Field Label]", "type": "[fileupload]", "help_text": "[Field-specific Instruction]", "id": "[Generated Field ID]"}
            ]
        },
    ]
}


class LLMPrompts:
    @staticmethod
    def pdf_to_json_prompt():
        """Prompt for converting PDF text to intermediary JSON, optimized for German forms."""
        prompt = f"""
        You are an expert in document analysis and structured form modeling, specifically for German government forms (Anträge).
        As input, you are given a PDF that is an application form in German.

        As output, you will generate JSON that represents the form, using the structure in this example:
        {json.dumps(JSON_EXAMPLE, indent=4)}

        The application form consists of a series of Rectangular Areas.
        Every word on the form is part of a Rectangular Area.
        
        Each Rectangular Area is one of four types:
        - Section, which contains Fields for the user to fill out, possibly including help text.
        - Internal Use, which contains Fields for someone other than the user to fill out.
        - Instructions, which contains help text.
        - Other.

        A Section:
        - is a rectangular area of the PDF.
        - sometimes has a title (e.g., "Persönliche Daten", "Bankverbindung").
        - sometimes contains instructions for the user (e.g., "Bitte in Druckbuchstaben ausfüllen").
        - has at least one Field for the user to fill out, and usually at least several.
        - does not contain an Internal Use.

        An Internal Use (IMPORTANT for German forms):
        - is a small rectangular area of the PDF containing words like "Nur für Dienstgebrauch", "Nicht vom Antragsteller auszufüllen", "Wird von der Behörde ausgefüllt", "Amtlicher Vermerk", "Interne Vermerke", "Eingangsstempel", "Platz für Eingangsstempel", "Aktenzeichen", "Handzeichen", "Dienstsiegel", "Wegfallsgrund", "Wegfallsart" or similar.
        - is a small rectangular area of the PDF with a border separating it from the rest of the form.
        - is possibly in a different typeface than the rest of the form.
        - does not contain instructions for the user.
        - does not contain the title of the form.
        - probably does not contain more than 10 words.
        - probably has no more than 8 Fields.
        - is usually in a corner of the page.

        When deciding whether a Rectangular Area is an Internal Use, use the smallest possible rectangle satisfying the above criteria.
        Do not include any content from the Internal Use in the output.

        A Field is one of:
        - text box (Textfeld)
        - radio button (Optionsfeld)
        - checkbox (Kontrollkästchen)

        For fillable PDF files, extract dropdown options.
        
        In the PDF, help text and instructions can appear either above or to the left of the Field.
        If any help text or instructions are present in the PDF, include it verbatim in the JSON in the help_text field.

        Identify PDF Fields, labels (in German), help text (in German), and instructions (in German), and format the output as JSON.
        **CRITICAL RULE: Do NOT translate any text extracted from the PDF into English.** All titles, help_text, and labels MUST remain in the original German. Only the JSON keys and types (e.g., "radio_button") should be in English.

        Skip Fields requiring a social security number (Sozialversicherungsnummer, Rentenversicherungsnummer) or password.

        Group related Fields into Sections. Recognize and maintain German numbering/lettering for sections (e.g., "I.", "II.", "A)", "1.").

        Present the instructions in a well-organized layout. Use bullet points where appropriate.

        Detect repeating sections and mark them accordingly.
        A table is usually a repeating section.

        The possible output fields for the JSON are as follows (Types must be in English, but labels are German):
        1. **Address**: address (e.g., "Anschrift", "Wohnort", "Straße", "Hausnummer", "Postleitzahl"). Please collate them into a single field of type "address".
        2. **Currency**: Currency values (e.g., "Betrag", "Einkommen", "Euro", "EUR").
        3. **Checkbox**: Allows multiple selections. Collate options as one field of "checkbox" type.
        4. **Date**: Captures dates (e.g., "Datum", "Geburtsdatum").
        5. **Email**: email address.
        6. **File Upload**: File attachments (e.g., "Anlagen", "Nachweise").
        7. **Name**: A person's name. Please collate "Vorname", "Nachname" into a single "name" type field.
        8. **Number**: Integer values (e.g., "Anzahl").
        9. **Radio Button**: Single selection from short lists (e.g., "Ja/Nein").
        10. **Text**: Open-ended text field.
        11. **Phone**: phone numbers ("Telefon").
        12.  If you see a field you do not understand, please use "unknown" as the type.

        Output only JSON, no explanations.
        """
        return prompt

    @staticmethod
    def fix_malformed_json_prompt(text):
            """Prompt for repair of malformed JSON."""
            prompt = f"""
            You are an expert in government forms. Process the following malformed extracted json from a government form to the correct output format:
            {text}
            Instructions:
            You will receive a JSON string that may be truncated, improperly formatted, or missing closing brackets/braces.
            Your job is to repair the JSON while preserving all original data.
            Ensure that:
            Every opening bracket '{{' or [ has a corresponding closing bracket '}}' or ].
            No JSON keys or values are lost.
            The output remains structurally valid and well-formed.
            Do NOT modify field values or alter key names. Only fix structural issues.
            If a portion of the JSON is ambiguous due to truncation, make a best-guess correction while maintaining logical consistency.
            **Output Rules:**
            - Output ONLY the corrected JSON—do NOT add explanations or comments.
            - Ensure the JSON can be parsed without errors in standard JSON libraries.
            """
            return prompt

    @staticmethod
    def post_process_json_prompt(text):
        """Post-processes extracted German JSON to collate fields correctly."""
        prompt = f"""
        You are an expert in German government forms. Process the following extracted json to be easier to use:
        
        {text}
        
        Make sure to consider the following rules to process the json:
        
        1. Do NOT create nested sections.
        2. Within each section, If you find separate fields for "Vorname", "Nachname", "Name", "Zuname" etc., you must collate them into a single 'name' type field.
        3. Within each section, If you find separate address related fields for "Straße", "Hausnummer", "Postleitzahl" (PLZ), "Wohnort", "Ort", "Stadt", etc., you must collate them into a single 'address' type field.
        4. For each "repeating_section", create an "entity_nickname" field which best describes the entity in German (e.g., "Person", "Kind", "Vermieter").
        5. Make sure IDs are unique across the entire form.
        6. Any text field that can be a number (integer) must be corrected to a number type.
        7. If necessary, create an additional new section with ONE fileupload field for text/checkbox fields that can be file attachments.
        8. Every section must have a title in German.
        9. Remove any fields for social security numbers or passwords.
        10. Condense each help text to no more than 400 characters. 
        11. Remove the section if there are no fields in it.
        12. Every Radio Button question must have at least two options.
        13. Every checkbox question must have at least one option.
        14. Every checkbox and radio button question should have some help text.
        
        Output JSON structure should match this example:
        {json.dumps(JSON_EXAMPLE, indent=4)}

        Output only JSON, no explanations.
        """
        return prompt
