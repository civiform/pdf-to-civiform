from google import genai
from google.genai import types
import json
from LLM_prompts import LLMPrompts
import logging
import os
import pymupdf
import re
import traceback

# OCR layer for scanned / flat PDFs
from ocr_lib import extract_text_from_pdf, detect_pdf_type

PAGE_LIMIT=5

def initialize_gemini_client(
    api_key=None,
    api_key_file=os.path.expanduser("~/google_api_key")):
    """
    Initializes and configures the Gemini GenerativeModel.

    Args:
        api_key (str, optional): API key provided by the user. Defaults to None.
        api_key_file (str): The path to the file containing the Google API key.

    Returns:
        genai.Client: The initialized Gemini client.
    """

    try:
        loaded_api_key = None
        if api_key:
            loaded_api_key = api_key
            logging.info("Using Gemini API key provided directly.")
        else:
            try:
                with open(api_key_file, "r") as f:
                    loaded_api_key = f.read().strip()
                logging.info(f"Google API key loaded successfully from file: {api_key_file}")
            except FileNotFoundError:
                logging.error(
                    f"Error: Google API key file not found at {api_key_file} and no key provided directly."
                )
                return None
            except Exception as e:
                logging.error(f"Error loading Google API key from file '{api_key_file}': {e}")
                return None

        if not loaded_api_key:
             logging.error("No Google API key available.")
             return None

        client = genai.Client(api_key=loaded_api_key)
        logging.info(f"Gemini client initialized successfully.")
        return client

    except Exception as e:
        logging.error(f"Error initializing Gemini client: {e}")
        logging.error(traceback.format_exc()) # Added traceback logging for init errors
        return None

def get_pdf_page_count(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return len(doc)

def extract_pages_as_bytes(pdf_bytes, start_page, end_page):
    """Extracts a range of pages and returns them as bytes."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    new_doc = pymupdf.open()

    for page_num in range(start_page, end_page):
        if page_num < len(doc):
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

    return new_doc.write()

def fix_malformed_json(json_str, client, model_name):
    try:
        json.loads(json_str)
        return json_str.strip()
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        # Attempt to fix by adding missing closing brackets/braces
        fix_malformed_json = LLMPrompts.fix_malformed_json_prompt(json_str)
        fixed_json_str = client.models.generate_content(model=model_name, contents=[fix_malformed_json])
        fixed_json_str = fixed_json_str.text.strip("`").lstrip("json")
        try:
            json.loads(fixed_json_str)
            return fixed_json_str.strip()
        except json.JSONDecodeError:
            print("Failed to auto-fix JSON. Manual review needed.")
            return None

def process_pdf_text_with_llm(
    client, model_name, file, base_name, work_dir,
    force_ocr=False, vision_client=None
):
    """
    Sends PDF content to Gemini and asks it to format the content into
    structured JSON.

    For DIGITAL PDFs (selectable text layer), the original multipart bytes
    path is used — the raw PDF is sent directly to Gemini.

    For SCANNED / FLAT PDFs (no text layer), Google Cloud Vision OCR is run
    first to extract text, which is then sent to Gemini as a text prompt.

    Args:
        client:         Initialized genai.Client.
        model_name:     Gemini model name.
        file:           Raw PDF bytes.
        base_name:      Short filename for output files.
        work_dir:       Base output directory.
        force_ocr:      If True, always run Cloud Vision OCR regardless of
                        PDF type detection. Useful for testing.
        vision_client:  Optional pre-built Vision ImageAnnotatorClient.

    Returns:
        (full_response_str, error_str) — error_str is None on success.
    """
    logging.info(f"LLM processing input extracted from PDF...")

    try:
        if not model_name.startswith("models/"):
            api_model_name = f"models/{model_name}"
        else:
            api_model_name = model_name

        # ── Step 1: Detect PDF type and extract text if needed ─────────────────
        pdf_type = "scanned" if force_ocr else detect_pdf_type(file)
        ocr_used = False
        ocr_char_count = 0

        if pdf_type == "scanned":
            # SCANNED PATH: run Cloud Vision OCR, then send text to Gemini
            logging.info("Using Cloud Vision OCR path for scanned PDF.")
            try:
                extracted_text, _ = extract_text_from_pdf(
                    file,
                    force_ocr=True,
                    vision_client=vision_client,
                )
                ocr_used = True
                ocr_char_count = len(extracted_text)
            except RuntimeError as ocr_err:
                logging.error(f"Cloud Vision OCR unavailable: {ocr_err}")
                logging.warning("Falling back to direct PDF bytes path (may fail for scanned PDFs).")
                pdf_type = "digital"  # fall back to bytes path

        responses = []
        page_count = get_pdf_page_count(file)
        logging.info(f"Page count: {page_count}")

        if pdf_type == "scanned" and ocr_used:
            # ── SCANNED: send extracted text to Gemini as a text prompt ────────
            prompt = LLMPrompts.pdf_to_json_prompt_from_text(
                extracted_text, pdf_type="scanned"
            )
            logging.info(f"Sending OCR text ({ocr_char_count} chars) to Gemini...")
            response = client.models.generate_content(
                model=api_model_name,
                contents=[prompt]
            )
            response_text = _extract_response_text(response)
            if response_text is None:
                return None, "Failed to extract text from LLM response (scanned path)"

            try:
                json_response = json.loads(response_text.strip())
                save_response_to_file(
                    response_text.strip(), base_name,
                    f"pdf-extract-ocr-{model_name}", work_dir
                )
                responses.append(json_response)
            except json.JSONDecodeError:
                logging.warning("Malformed JSON from scanned path; attempting repair...")
                fixed = fix_malformed_json(response_text, client, model_name)
                if fixed:
                    responses.append(json.loads(fixed))
                else:
                    return None, "Gemini returned malformed JSON that could not be repaired."

        else:
            # ── DIGITAL: original multipart PDF bytes path (unchanged) ─────────
            prompt = LLMPrompts.pdf_to_json_prompt()
            logging.debug("Sending PDF bytes directly to Gemini (digital path)...")

            input_file = types.Part.from_bytes(data=file, mime_type="application/pdf")
            response = client.models.generate_content(
                model=api_model_name,
                contents=[input_file, prompt]
            )
            response_text = _extract_response_text(response)
            if response_text is None:
                return None, "Failed to extract text from LLM response (digital path)"

            try:
                json_response = json.loads(response_text.strip())
                save_response_to_file(
                    response_text.strip(), base_name,
                    f"pdf-extract-{model_name}", work_dir
                )
                responses.append(json_response)
            except json.JSONDecodeError:
                logging.warning("Malformed JSON from digital path; processing in batches...")

                for start in range(0, page_count, PAGE_LIMIT):
                    end = min(start + PAGE_LIMIT, page_count)
                    chunk_bytes = extract_pages_as_bytes(file, start, end)
                    chunk_input = types.Part.from_bytes(
                        data=chunk_bytes, mime_type="application/pdf"
                    )
                    response = client.models.generate_content(
                        model=api_model_name,
                        contents=[chunk_input, prompt],
                    )
                    response_text = _extract_response_text(response)
                    if response_text is None:
                        logging.error(f"LLM response failed for pages {start}-{end}; skipping.")
                        continue

                    fixed_text_response = fix_malformed_json(response_text, client, model_name)
                    if fixed_text_response is not None:
                        try:
                            fixed_json = json.loads(fixed_text_response.strip())
                            save_response_to_file(
                                fixed_text_response.strip(), base_name,
                                f"pdf-extract-{start}-{model_name}", work_dir,
                            )
                            responses.append(fixed_json)
                        except json.JSONDecodeError:
                            logging.warning(f"Skipping malformed JSON for pages {start}-{end}")
                    else:
                        logging.warning(f"Skipping malformed JSON for pages {start}-{end}")

        # ── Step 2: Annotate with extraction metadata ──────────────────────────
        # Inject a top-level _extraction_metadata block so the UI can display
        # badges like "Detected: Scanned PDF — Cloud Vision OCR used".
        if responses:
            for resp in responses:
                if isinstance(resp, dict):
                    resp["_extraction_metadata"] = {
                        "pdf_type": pdf_type,
                        "ocr_used": ocr_used,
                        "model": model_name,
                        "ocr_char_count": ocr_char_count,
                    }

        full_response = json.dumps(responses, ensure_ascii=False, indent=4)
        save_response_to_file(full_response, base_name, f"pdf-extract-{model_name}", work_dir)
        return full_response, None

    except Exception as e:
        error_details = f"Error in process_pdf_text_with_llm (model: {api_model_name}): {type(e).__name__} - {e}"
        logging.error(error_details)
        logging.error(traceback.format_exc())
        return None, error_details


def _extract_response_text(response) -> str | None:
    """Robustly pull the text string out of a genai response object."""
    if hasattr(response, 'text'):
        return response.text.strip("`").lstrip("json")
    elif (
        hasattr(response, 'candidates') and response.candidates and
        hasattr(response.candidates[0], 'content') and
        response.candidates[0].content.parts
    ):
        return (
            response.candidates[0].content.parts[0].text
            .strip("`")
            .lstrip("json")
            .strip()
        )
    logging.error(f"Could not extract text from LLM response. Object: {response}")
    return None

def save_response_to_file(response, base_name, output_suffix, output_directory):
    """
    Saves a given response string to a file inside the specified output directory.
    Assumes the directory already exists.

    Args:
        response (str): The string to be saved to the file.
        base_name (str): The base name of the file.
        output_suffix (str): The suffix to append to the filename.
        output_directory (str): The absolute path to the directory where the file should be saved.
    """
    try:
        # Construct the path using the provided output directory
        output_file_full = os.path.join(
            output_directory, f"{base_name}-{output_suffix}.json") # Use output_directory parameter

        # Clean the response
        cleaned_response = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', response, flags=re.IGNORECASE)

        # Save the file
        with open(output_file_full, "w", encoding="utf-8") as f:
            f.write(cleaned_response)

        logging.info(f"{output_suffix} Response saved to: {output_file_full}")

    except Exception as e:
        logging.error(f"Error saving response to file '{output_file_full}': {e}")
        logging.error(traceback.format_exc())
    
def chunk_text(text, base_name, model_name):
    """Splits JSON text into well-formed chunks based on title, help_text, and sections."""
    try:
        json_obj = json.loads(text)  # Validate input JSON
    except json.JSONDecodeError:
        logging.error("Invalid JSON input provided. Cannot split malformed JSON.")
        return []

    logging.info("Starting chunking of JSON")

    # Ensure json_obj is not empty
    if not json_obj:
        logging.error("Empty JSON object provided for chunking.")
        return []

    chunks = []
    for i, obj in enumerate(json_obj):
      chunk = {
        "title": obj.get("title", ""),
        "help_text": obj.get("help_text", ""),
        "sections": obj.get("sections", [])
      }
      chunks.append(chunk)
    return chunks

def post_processing_llm(client, model_name, text, base_name, output_json_dir):
    """Sends extracted json text to Gemini and asks it to collate related fields into appropriate civiform types, in particular names and address."""
    prompt_post_processing_json = LLMPrompts.post_process_json_prompt(text)

    try:
        chunks = chunk_text(text, base_name, model_name)
        aggregated_responses  = []   # Store processed responses as a single dictionary
        logging.info("post_processing_json_with_llm: Collating names, addresses ...")

        if not model_name.startswith("models/"):
            api_model_name = f"models/{model_name}"
        else:
            api_model_name = model_name
        for i, chunk in enumerate(chunks):
            prompt_post_processing_json = LLMPrompts.post_process_json_prompt(chunk)

            response = client.models.generate_content(
                model=api_model_name,
                contents=[prompt_post_processing_json]
                # TODO add safety_settings here
                )

            # Extract text robustly, similar to process_pdf_text_with_llm
            if hasattr(response, 'text'):
                 response_text = response.text.strip("`").lstrip(
                     "json")
            elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts:
                 response_text = response.candidates[0].content.parts[0].text.strip("`").lstrip("json").strip()
            else:
                 logging.error(f"Could not extract text from LLM post-processing response. Response object: {response}")
                 return None # Treat as failure

            aggregated_responses.append(json.loads(response_text))

        result=json.dumps(aggregated_responses, ensure_ascii=False, indent=4)
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
          save_response_to_file(result, base_name, f"post-processed-{model_name}", output_json_dir)
        return result  # Return as a formatted JSON string


    except Exception as e:
        error_details = f"Error during collating fields (model: {api_model_name}): {type(e).__name__} - {e}"
        logging.error(error_details)
        logging.error(traceback.format_exc()) # Log full traceback
        return None
