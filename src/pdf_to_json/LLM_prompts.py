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
        """Prompt for converting PDF text to intermediary JSON."""
        prompt = f"""
        You are an expert in document analysis and structured form modeling.  
        As input, you are given a PDF that is an application form.

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
        - sometimes has a title.
        - sometimes contains instructions for the user.
        - has at least one Field for the user to fill out, and usually at least several.
        - does not contain an Internal Use.

        An Internal Use:
        - is a small rectangular area of the PDF containing the words "For Office Use", "For Administrative Use", "For Agency Use", "Use Only" or similar.
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
        - text box
        - radio button
        - checkbox

        For fillable PDF files, extract dropdown options.
        
        In the PDF, help text and instructions can appear either above or to the left of the Field.
        If any help text or instructions are present in the PDF, include it verbatim in the JSON in the help_text field.

        Identify PDF Fields, labels, help text, and instructions, and format the output as JSON.
        Skip Fields requiring a social security number or password.

        Group related Fields into Sections.

        Present the instructions in a well-organized layout. Use bullet points where appropriate.

        Detect repeating sections and mark them accordingly.
        A table is usually a repeating section.

        The possible output fields for the JSON are as follows:
        1. **Address**: address (e.g., residential, work, mailing). Unit, city, zip code, street, municipality, county, district etc are included. Please collate them into a single field.
        2. **Currency**: Currency values with decimal separators (e.g., income, debts).
        3. **Checkbox**: Allows multiple selections (e.g., ethnicity, available benefits, languages spoken etc). Collate options for checkboxes as one field of "checkbox" type if possible. Checkbox options must be unique. Every checkbox must have at least one option. Options cannot be empty strings.
        4. **Date**: Captures dates (e.g., birth date, graduation date, month, year etc).
        5. **Email**: email address. Please collate domain and username if asked separately.
        6. **File Upload**: File attachments (e.g., PDFs, images)
        7. **Name**: A person's name. Please collate first name, middle name, and last name into full name.
        8. **Number**: Integer values e.g., number of household members etc.
        9. **Radio Button**: Single selection from short lists (<=7 items, e.g., Yes/No questions). Every Radio Button questions must have at least two options.
        10. **Text**: Open-ended text field for letters, alphanumerics, or symbols.
        11. **Phone**: phone numbers.
        12.  If you see a field you do not understand, please use "unknown" as the type, associate nearby text as help text and assign a unique ID.

        Output only JSON, no explanations.
        """
        return prompt

    @staticmethod
    def fix_malformed_json_prompt(text):
            """Prompt for converting PDF text to intermediary JSON."""
            prompt = f"""
            You are an expert in government forms.  Process the following malformed extracted json from a government form to the correct output format:
            {text}
            Instructions:
            You will receive a JSON string that may be truncated, improperly formatted, or missing closing brackets/braces.
            Your job is to repair the JSON while preserving all original data.
            Ensure that:
            Every opening bracket '{' or [ has a corresponding closing bracket '}' or ].
            No JSON keys or values are lost.
            The output remains structurally valid and well-formed.
            Do NOT modify field values or alter key names. Only fix structural issues.
            If a portion of the JSON is ambiguous due to truncation, make a best-guess correction while maintaining logical consistency.
            **Output Rules:**
            - Output ONLY the corrected JSON—do NOT add explanations or comments.
            - Ensure the JSON can be parsed without errors in standard JSON libraries.
            """
            return prompt

# TODO: Redundant instructions for radio button and checkbox were added as the LLM did not always follow the instructions in the step 1 LLM processing prompt
    @staticmethod
    def post_process_json_prompt(text):
        """Sends extracted json text to Gemini and asks it to collate related fields into appropriate civiform types, in particular names and address."""
        #  TODO: could not reliably move repeating sections out of sections without LLM creating unnecessary repeating sections.
        
        prompt = f"""
        You are an expert in government forms.  Process the following extracted json from a government form to be easier to use:
        
        {text}
        
        Make sure to consider the following rules to process the json:
        
        1. Do NOT create nested sections.
        2. Within each section, If you find separate fields for first name, middle name, and last name, you must collate them into a single 'name' type field. Please DO NOT create separate fields for name fields.
        3. Within each section, If you find separate address related fields for unit, city, zip code, street, municipality, county, district etc, you must collate them into a single 'address' type field. Please DO NOT create separate fields for address components. However, do separate mailing address from physical address.
        4. For each "repeating_section", create an "entity_nickname" field which best describes the entity that the repeating entries are about.
        5. Make sure IDs are unique across the entire form.
        6. Any text field that can be a number (integer) must be corrected to a number type - such as frequency etc.
        7. If necessary, create an additional new section with ONE fileupload field for text/checkbox fields that can be file attachments.
        8. Every section must have a title.
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
