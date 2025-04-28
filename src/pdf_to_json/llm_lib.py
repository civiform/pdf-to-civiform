from google import genai
from google.genai import types
import json
from LLM_prompts import LLMPrompts
import logging
import os
import pymupdf
import re

def initialize_gemini_model(
    model_name="gemini-2.0-flash",
    api_key=None,
    api_key_file=os.path.expanduser("~/google_api_key")):
    """
    Initializes and configures the Gemini GenerativeModel.

    Args:
        model_name (str): The name of the Gemini model to use.
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

def process_pdf_text_with_llm(client, model_name, file, base_name, work_dir):
    """Sends extracted PDF text to Gemini and asks it to format the content into structured JSON."""

    prompt = LLMPrompts.pdf_to_json_prompt()
    logging.info(f"LLM processing input txt extracted from PDF...")

    try:
        logging.debug(f"Sending PDF to LLM...")
        page_count = get_pdf_page_count(file)
        logging.info(f"Page count {page_count}")
        responses = []

        if not model_name.startswith("models/"):
            api_model_name = f"models/{model_name}"
        else:
            api_model_name = model_name

        input_file = types.Part.from_bytes(data=file, mime_type="application/pdf")
        response = client.models.generate_content(
            model=api_model_name,
            contents=[input_file, prompt]
        )

        # Add robust check based on actual library behavior
        if hasattr(response, 'text'):
            response_text = response.text.strip("`").lstrip("json")  # Remove ``` and "json" if present
        elif (
            hasattr(response, 'candidates') and response.candidates and
            hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts
        ):
            # Fallback to candidate structure if .text isn't available (more typical)
            response_text = (
                response.candidates[0].content.parts[0].text
                .strip("`")
                .lstrip("json")
                .strip()
            )
        else:
            # Cannot extract text, log the response structure for debugging
            logging.error(f"Could not extract text from LLM response. Response object: {response}")
            return None, "Failed to extract text from LLM response"

        try:
          json_response = json.loads(response_text.strip())
          save_response_to_file(response_text.strip(),
                                base_name,
                                f"pdf-extract-{model_name}",
                                work_dir)
          responses.append(json_response)
        except json.JSONDecodeError:
          logging.warning("Malformed json, needs processing in batches..")

          for start in range(0, page_count, PAGE_LIMIT):
              end = min(start + PAGE_LIMIT, page_count)
              chunk_bytes = extract_pages_as_bytes(file, start, end)

              input_file = types.Part.from_bytes(
                  data=chunk_bytes, mime_type="application/pdf"
              )

              response = client.models.generate_content(
                  model=api_model_name,
                  contents=[input_file, prompt],
              )

              # Add robust check based on actual library behavior
              if hasattr(response, 'text'):
                  response_text = response.text.strip("`").lstrip("json")  # Remove ``` and "json" if present
              elif (
                  hasattr(response, 'candidates') and response.candidates and
                  hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts
              ):
                  # Fallback to candidate structure if .text isn't available (more typical)
                  response_text = (
                      response.candidates[0].content.parts[0].text
                      .strip("`")
                      .lstrip("json")
                      .strip()
                  )
              else:
                  # Cannot extract text, log the response structure for debugging
                  logging.error(f"Could not extract text from LLM response. Response object: {response}")
                  return None, "Failed to extract text from LLM response"

              fixed_text_response = fix_malformed_json(response_text, client, model_name)
              if fixed_text_response is not None:
                  try:
                      fixed_json = json.loads(fixed_text_response.strip())
                      save_response_to_file(
                          fixed_text_response.strip(),
                          base_name,
                          f"pdf-extract-{start}-{model_name}",
                          work_dir,
                      )
                      responses.append(fixed_json)
                  except json.JSONDecodeError:
                      logging.warning(f"Skipping malformed JSON for pages {start}-{end}")
              else:
                  logging.warning(f"Skipping malformed JSON for pages {start}-{end}")

        full_response = json.dumps(responses, ensure_ascii=False, indent=4)
        save_response_to_file(full_response, base_name, f"pdf-extract-{model_name}", work_dir)
        return full_response, None # Return response and None for error

    except Exception as e:
        error_details = f"Error in process_pdf_text_with_llm (model: {api_model_name}): {type(e).__name__} - {e}"
        logging.error(error_details)
        logging.error(traceback.format_exc()) # Log full traceback
        return None, error_details # Return None for response and the error details

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

def post_processing_llm(client, model_name, text, base_name):
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
          llm.save_response_to_file(result, base_name, f"post-processed-{model_name}", output_json_dir)
        return result  # Return as a formatted JSON string


    except Exception as e:
        error_details = f"Error during collating fields (model: {api_model_name}): {type(e).__name__} - {e}"
        logging.error(error_details)
        logging.error(traceback.format_exc()) # Log full traceback
        return None
