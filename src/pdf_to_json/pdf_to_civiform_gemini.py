from google import genai
from google.genai import types
from pathlib import Path
import json
import pymupdf
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import logging
import re
from convert_to_civiform_json import convert_to_civiform_json
from LLM_prompts import LLMPrompts
from io import StringIO
import traceback # Import the traceback module
import sys
import argparse # Import argparse

PAGE_LIMIT=5


# This script extracts text from uploaded PDF files, uses Gemini LLM to
# convert the text into structured JSON representing a form, formats the JSON
# for better readability, and then converts it into a CiviForm-compatible
# JSON format.  It uses a Flask web server to handle file uploads OR can be
# run from the command line to process a single file.

# make sure you have your gemini API key in ~/google_api_key
# install the latest geminiAPI package: pip install -U -q "google-genai"

# run web server: python pdf_to_civiform_gemini.py
# run command line: python pdf_to_civiform_gemini.py --input-file /path/to/file.pdf [--model-name model] [--log-level LEVEL]
# output files are stored in ~/pdf_to_civiform/output-json

# --- Global Configuration ---
DEFAULT_MODEL_NAME = "gemini-2.0-flash" # Default model used in initialize_gemini_model

# Configure logging (Initial setup, level can be changed later via CLI)
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Capture logging output for web display (if web server runs)
log_stream = StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(log_handler)

app = Flask(__name__)

# --- Directory Setup ---
try:
    work_dir = os.path.expanduser("~/pdf_to_civiform")
    if not os.path.isabs(work_dir): # Ensure we got an absolute path
        raise ValueError("Could not resolve home directory path.")

    default_upload_dir = os.path.join(work_dir, 'uploads')
    output_json_dir = os.path.join(work_dir, "output-json")

    os.makedirs(default_upload_dir, exist_ok=True)
    os.makedirs(output_json_dir, exist_ok=True)

    logging.info(f"Using base directory: {work_dir}")
    logging.info(f"upload directory: {default_upload_dir}")
    logging.info(f"json output directory: {output_json_dir}")

except (ValueError, OSError) as e:
    logging.error(f"Failed to setup required directories based on '~/pdf_to_civiform'. " \
          f"Check path and permissions. Error: {e}", file=sys.stderr)
    sys.exit(f"Startup failed: Directory setup error.")

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


def process_pdf_text_with_llm(client, model_name, file, base_name):
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
          save_response_to_file(result, base_name, f"post-processed-{model_name}", output_json_dir)
        return result  # Return as a formatted JSON string


    except Exception as e:
        error_details = f"Error during collating fields (model: {api_model_name}): {type(e).__name__} - {e}"
        logging.error(error_details)
        logging.error(traceback.format_exc()) # Log full traceback
        return None


def format_json_single_line_fields(json_string: str) -> str:
    """
    Formats a JSON string to ensure all field attributes (including options)
    are on a single line, while maintaining readability for nested structures.

    Args:
        json_string (str): The JSON string to format.

    Returns:
        str: The formatted JSON string.

    Raises:
        json.JSONDecodeError: If the input string is not valid JSON.
        ValueError: If an unexpected error occurs during formatting.
    """
    try:
        data = json.loads(json_string)

        def custom_dumps(obj, level=0):
            if isinstance(obj, dict):
                if "label" in obj and "type" in obj and "id" in obj:
                    # Format field objects on a single line
                    return json.dumps(
                        obj, separators=(',', ':'), sort_keys=False)
                else:
                    # Format other dictionaries with indentation
                    return "{\n" + "".join(
                        f"{'    ' * (level + 1)}{json.dumps(k, separators=(',', ':'), sort_keys=False)}: {custom_dumps(v, level + 1)},\n"
                        for k, v in obj.items())[:-2] + "\n" + (
                            "    " * level) + "}"
            elif isinstance(obj, list):
                # Format lists with indentation and single-line fields
                return "[\n" + "".join(
                    f"{'    ' * (level + 1)}{custom_dumps(item, level + 1)},\n"
                    for item in obj)[:-2] + "\n" + ("    " * level) + "]"
            else:
                return json.dumps(obj, separators=(',', ':'), sort_keys=False)

        return custom_dumps(data)

    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        raise  # Re-raise the exception to be handled by the caller
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise ValueError(
            f"An unexpected error occurred during JSON formatting: {e}"
        ) from e  # Raise a ValueError


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


def process_file(file_full, model_name, client):
    """
    Processes a single PDF file, extracts data, interacts with the LLM, and converts it to CiviForm JSON.

    Args:
        file_full (str): The full path to the PDF file.
        model_name (str): The name of the LLM model to use.
        client : The initialized Gemini client.

    Returns:
        dict: A dictionary containing 'intermediary_json' and 'civiform_json' strings, or None if processing fails.
    Raises:
        Exception: If LLM processing or post-processing fails.
    """
    try:
        # Extract the base filename without extension
        filename = os.path.basename(file_full)
        base_name, _ = os.path.splitext(filename)
        base_name = base_name[:
                              15]  # limit to 15 chars to avoid extremely long filenames
        logging.info(f"Processing file: {file_full} ...")

        filepath = Path(file_full)
        file_bytes = filepath.read_bytes()
        structured_json, llm_error = process_pdf_text_with_llm(
            client, model_name, file_bytes, base_name)

        if structured_json is None:
            raise Exception(f"LLM processing failed for file: {file_full}. Details: {llm_error}")

        logging.info(f"Formating json  .... ")
        formated_json = format_json_single_line_fields(structured_json)
        save_response_to_file(
            formated_json, base_name, f"formated-{model_name}", output_json_dir)

        post_processed_json = post_processing_llm(
            client, model_name, formated_json, base_name)
        if post_processed_json is None:
            raise Exception(f"LLM post-processing failed for file: {file_full}")

        logging.info(f"Formating post processed json  .... ")
        formated_post_processed_json = format_json_single_line_fields(
            post_processed_json)
        save_response_to_file(
            formated_post_processed_json, f"{base_name}-post-processed",
            f"formated-{model_name}", output_json_dir)

        parsed_json = json.loads(formated_post_processed_json)
        civiform_json = convert_to_civiform_json(parsed_json[0])
        save_response_to_file(
            civiform_json, base_name, f"civiform-{model_name}", output_json_dir)
        logging.info(f"Done processing file: {file_full}")

        # Return both the intermediary and CiviForm JSON
        return {
            "intermediary_json": formated_post_processed_json,
            "civiform_json": civiform_json
        }
    except Exception as e:
        logging.error(f"Failed to process file {file_full}: {e}")
        raise # Re-raise the exception to be caught in the route


@app.route('/')
def index():
    log_stream.seek(0)
    log_stream.truncate(0)
    return render_template('index.html', debug_log="")


@app.route('/upload', methods=['POST'])
def upload_file():
    log_stream.seek(0)
    log_stream.truncate(0)
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file.filename)
        file_full = os.path.join(default_upload_dir, filename)
        logging.info(f"Receiving file upload: {filename}")
        file.save(file_full)
        logging.info(f"File saved to: {file_full}")

        # Get LLM model name, API key, and log level from the request
        model_name = request.form.get('modelName', DEFAULT_MODEL_NAME) # Use default if not provided
        gemini_api_key = request.form.get('geminiApiKey')
        log_level_str = request.form.get('logLevel', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logging.getLogger().setLevel(log_level)
        logging.info(f"Log level set to: {logging.getLevelName(log_level)}")
        logging.info(f"Using model for request: {model_name}")

        client = initialize_gemini_model(model_name=model_name, api_key=gemini_api_key)
        if client is None:
            error_message = "Failed to initialize Gemini client. Check API key configuration and logs."
            logging.error(error_message)
            debug_log = log_stream.getvalue()
            return jsonify({"error": error_message, "debug_log": debug_log}), 500

        # Process the file
        processing_result = process_file(file_full, model_name, client)

        # Get logs generated during processing
        debug_log = log_stream.getvalue()

        if processing_result is None:
             error_message = f"Failed to process file '{filename}'."
             logging.error(error_message)
             return jsonify({"error": error_message, "debug_log": debug_log}), 500
        else:
            logging.info(f"Successfully processed '{filename}' via upload.")
            logging.info(f"Length of intermediary json: {len(processing_result.get('intermediary_json', ''))}")
            logging.info(f"Length of civiform_json: {len(processing_result.get('civiform_json', ''))}")
            # Return the dictionary containing both JSON strings
            response_data = {
                "intermediary_json": processing_result.get("intermediary_json"),
                "civiform_json": processing_result.get("civiform_json"),
            }
            return jsonify(response_data)

    except Exception as e:
        error_message = f"An unexpected error occurred during file upload/processing: {e}"
        logging.error(error_message)
        logging.error(traceback.format_exc()) # Log full traceback
        debug_log = log_stream.getvalue()
        return jsonify({"error": error_message, "details": traceback.format_exc(), "debug_log": debug_log}), 500

@app.route('/convert_to_civiform', methods=['POST'])
def handle_convert_to_civiform():
    """
    Endpoint to convert intermediary JSON (provided in request body)
    to CiviForm JSON.
    """
    log_stream.seek(0)
    log_stream.truncate(0)
    logging.info("Received request to convert intermediary JSON to CiviForm JSON.")

    if not request.is_json:
        logging.error("Request content type is not application/json")
        return jsonify({"error": "Request must be JSON"}), 415

    try:
        request_data = request.get_json()
        intermediary_json_str = request_data.get('intermediary_json')

        if not intermediary_json_str:
            logging.error("No 'intermediary_json' field found in request.")
            return jsonify({"error": "Missing 'intermediary_json' in request body"}), 400

        # Parse the intermediary JSON string provided by the client
        try:
            intermediary_data = json.loads(intermediary_json_str)
            logging.info("Successfully parsed intermediary JSON from request.")
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON received in 'intermediary_json': {e}")
            return jsonify({"error": "Invalid JSON format provided in 'intermediary_json'", "details": str(e)}), 400

        # Check if the parsed data is a list and extract the first element if needed
        data_to_convert = None
        if isinstance(intermediary_data, list):
            if not intermediary_data:
                logging.error("Intermediary data list is empty.")
                return jsonify({"error": "Intermediary JSON data is an empty list"}), 400
            # Assume the relevant data is the first element of the list
            data_to_convert = intermediary_data[0]
        elif isinstance(intermediary_data, dict):
             data_to_convert = intermediary_data
             logging.info("Intermediary data is a dictionary, using it directly for conversion.")
        else:
             logging.error(f"Intermediary data is not a list or dict, type is {type(intermediary_data)}")
             return jsonify({"error": "Unexpected format for intermediary JSON data"}), 400

        if not isinstance(data_to_convert, dict):
             logging.error(f"Data selected for conversion is not a dictionary (type: {type(data_to_convert)}). Cannot proceed.")
             return jsonify({"error": "Selected data for conversion is not in the expected dictionary format."}), 400

        # Perform the conversion
        civiform_json_result = convert_to_civiform_json(data_to_convert)
        logging.info("Conversion to CiviForm JSON successful.")

        # Return the resulting CiviForm JSON string
        return jsonify({"civiform_json": civiform_json_result})

    except Exception as e:
        error_message = f"An error occurred during CiviForm JSON conversion: {e}"
        logging.error(error_message)
        logging.error(traceback.format_exc())
        return jsonify({"error": error_message, "details": traceback.format_exc()}), 500


def process_directory(directory, model_name, client):
    """
    Processes all PDF files in a given directory and returns summary information.
    NOTE: This function currently does *not* return the individual JSON outputs,
          only success/failure status per file. Modifying it to return all JSONs
          could lead to very large responses.

    Args:
        directory (str): The path to the directory containing PDF files.
        model_name (str): The name of the LLM model to use.
        client: The initialized Gemini client.

    Returns:
        dict: Dictionary containing summary details (total, success, fail, file_results).
    """
    success_count = 0
    fail_count = 0
    total_files = 0

    abs_directory = os.path.abspath(os.path.expanduser(directory))
    if not abs_directory.startswith(os.path.abspath(work_dir)):
        logging.error(
            f"Attempted access outside working directory: {directory}")
        return {
            "total_files": 0, "success_count": 0, "fail_count": 0, "file_results": {}
        }

    file_results = {}
    logging.info(f"--- Processing Directory: {abs_directory} ---")

    if not os.path.isdir(abs_directory):
         logging.error(f"Directory not found: {abs_directory}")
         return {"total_files": 0, "success_count": 0, "fail_count": 0, "file_results": {}}


    for filename in os.listdir(abs_directory):
        if filename.lower().endswith(".pdf"):
            total_files += 1
            file_full = os.path.join(abs_directory, filename)
            file_results[filename] = {"success": False, "error_message": ""}
            try:
                processing_output = process_file(file_full, model_name, client)
                if processing_output and processing_output.get("civiform_json"):
                    success_count += 1
                    file_results[filename]["success"] = True
                else:
                    fail_count += 1
                    file_results[filename]["error_message"] = "Failed to process file."
            except Exception as e:
                fail_count += 1
                error_message = f"Error processing {filename}: {e}"
                file_results[filename]["error_message"] = error_message
                logging.error(f"Error during directory processing for {filename}: {e}\n{traceback.format_exc()}")

    logging.info(f"--- Directory Processing Complete: {abs_directory} ---")
    logging.info(f"Summary: Total={total_files}, Success={success_count}, Failed={fail_count}")

    current_debug_log = log_stream.getvalue()
    log_stream.seek(0)
    log_stream.truncate(0) # Clear stream after reading

    return {
        "total_files": total_files,
        "success_count": success_count,
        "fail_count": fail_count,
        "file_results": file_results,
        "debug_log": current_debug_log
    }


@app.route('/upload_directory', methods=['POST'])
def upload_directory():
    """
    Endpoint to process a directory of files and return a summary.
    """

    log_stream.seek(0)
    log_stream.truncate(0)
    logging.info("Received request to process directory.")

    # Get LLM model name, API key, and log level from the request
    model_name = request.form.get('modelName', DEFAULT_MODEL_NAME)
    gemini_api_key = request.form.get('geminiApiKey')
    log_level_str = request.form.get('logLevel', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.getLogger().setLevel(log_level)
    logging.info(f"Log level set to: {logging.getLevelName(log_level)}")
    logging.info(f"Using model for request: {model_name}")


    directory_path_input = request.form.get('directoryPath', default_upload_dir) # Use default if not provided
    directory_path = os.path.abspath(os.path.expanduser(directory_path_input))

    # Basic check to prevent accessing outside of the work dir
    if not directory_path.startswith(work_dir):
        logging.error(f"Requested directory outside work directory: {directory_path}")
        debug_log = log_stream.getvalue() # Capture log before returning error
        return jsonify({"error": "Invalid directory path.", "debug_log": debug_log}), 400

    if not os.path.isdir(directory_path):
        logging.error(f"Invalid directory path: {directory_path}")
        debug_log = log_stream.getvalue()
        return jsonify({"error": "Invalid directory path.", "debug_log": debug_log}), 400


    client = initialize_gemini_model(model_name, api_key=gemini_api_key)
    if client is None:
        error_message = "Failed to initialize Gemini client. Check API key or file."
        logging.error(error_message)
        debug_log = log_stream.getvalue()
        return jsonify({"error": error_message, "debug_log": debug_log}), 500

    try:
        directory_result = process_directory(directory_path, model_name, client)
        debug_log = directory_result.get("debug_log", "No debug log captured.")

        response_data = {
            "summary": {
                "processed_directory": directory_path,
                "total_files": directory_result["total_files"],
                "success_count": directory_result["success_count"],
                "fail_count": directory_result["fail_count"],
                "file_results": directory_result["file_results"]
            },
        }
        logging.info(f"Directory processing finished for: {directory_path}")
        return jsonify(response_data)
    except Exception as e:
        error_message = f"An error occurred during directory processing: {e}"
        logging.error(f"{error_message}\n{traceback.format_exc()}")
        debug_log = log_stream.getvalue()
        return jsonify({"error": error_message, "details": traceback.format_exc(), "debug_log": debug_log}), 500


# --- Main Execution Block ---

if __name__ == '__main__':
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(
        description="Process a PDF form file to CiviForm JSON using Gemini LLM. Runs as a web server if --input-file is not provided.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

    parser.add_argument(
        '--input-file',
        type=str,
        default=None, # Default is None, indicating web server mode
        help='Path to a single PDF file to process (activates command-line mode).'
        )
    parser.add_argument(
        '--model-name',
        type=str,
        default=DEFAULT_MODEL_NAME, # Use the global default
        help='Name of the Gemini model to use (e.g., gemini-1.5-flash, gemini-pro).'
        )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level for console output in command-line mode.'
        )

    args = parser.parse_args()

    # --- Conditional Execution: Command Line or Web Server ---
    if args.input_file:
        # --- Command Line Mode ---
        logging.info("--- Running in Command Line Mode ---")

        # Set log level based on command line arg for console output
        log_level_cli = getattr(logging, args.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level_cli) # Set root logger level
        for handler in logging.getLogger().handlers:
             if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr or handler.stream == sys.stdout:
                   handler.setLevel(log_level_cli)
        logging.info(f"Console log level set to: {args.log_level}")

        # Validate input file path
        input_path = os.path.abspath(os.path.expanduser(args.input_file))
        if not os.path.isfile(input_path):
            logging.error(f"Input file not found or is not a file: {input_path}")
            sys.exit(1) # Exit with error code

        # Initialize Gemini Client using the specified model name
        # API key is handled internally by the function (reading from file)
        logging.info(f"Initializing Gemini client for model: {args.model_name}")
        client = initialize_gemini_model(model_name=args.model_name) # Pass only model name
        if client is None:
            logging.error("Failed to initialize Gemini client. Check API key file/access. Exiting.")
            sys.exit(1)

        # Process the single file
        try:
            result_dict = process_file(
                file_full=input_path,
                model_name=args.model_name, # Pass model name
                client=client               # Pass initialized client
            )
            if result_dict and result_dict.get("civiform_json"):
                logging.info(f"Successfully processed '{args.input_file}'.")
                logging.info(f"Final CiviForm JSON saved in '{output_json_dir}'.")
                sys.exit(0)
            else:
                 logging.error(f"Command-line processing completed for '{args.input_file}' but failed to generate required JSON output.")
                 sys.exit(1)


        except Exception as e:
            logging.error(f"Command-line processing failed for '{args.input_file}'. See logs above for details.")
            logging.error(traceback.format_exc())
            sys.exit(1) # Exit with error code

    else:
        # --- Web Server Mode ---
        # No --input-file provided, run the Flask app
        logging.info("--- Running in Web Server Mode ---")
        logging.info(f"Starting Flask server...")
        app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 7000)))
