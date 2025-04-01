# PDF to CiviForm

This is a prototype transforming an input PDF containing government forms to CiviForm JSON format.
Relevant documentation and active work items are captured in this epic: [https://github.com/civiform/civiform/issues/9967](https://github.com/civiform/civiform/issues/9967)

## How to run
### setup
1.  **Gemini API Key**: Make sure you have your Gemini API key saved in a file named `google_api_key` in your home directory (`~/google_api_key`). (Instructions: [https://ai.google.dev/gemini-api/docs/quickstart?lang=python](https://ai.google.dev/gemini-api/docs/quickstart?lang=python))
2.  **Python Environment**: This script requires Python 3.x.
3.  **Dependencies**: Install dependencies: "pip install -r python_dependencies.txt "


## Running the Application

You can run this tool either as a web server for interactive use or directly from the command line for processing single files.

### Option 1: Run as a Web Server

This is the default mode if no input file is specified.

1.  You can use ```bin/build-dev``` and ```bin/run-dev``` to build and run the application in a container; or navigate to the directory containing the script ```/workspaces/pdf-to-civiform/src/pdf_to_json``` and run the script ```python pdf_to_civiform_gemini.py``` locally.
3.  The script will start a Flask web server. Open your web browser and go to ``` http://localhost:7000/```
4.  Use the web interface to upload a PDF file, select options (like model name, log level), and trigger the conversion process.

### Option 2: Run from Command Line (Single File)

This mode processes a single PDF file directly without starting the web server.

1.  Navigate to the directory containing the script: ```/workspaces/pdf-to-civiform/src/pdf_to_json```
2.  Run the script using the `--input-file` argument, specifying the path to your PDF:
    ```python pdf_to_civiform_gemini.py --input-file /path/to/your/form.pdf [options]```

**Command-Line Arguments:**

* `--input-file <path>`: The full path to the PDF file you want to process. 
* `--model-name <model_id>`: (Optional) The Gemini model to use (e.g., `gemini-1.5-pro`, `gemini-2.0-flash`). Defaults to `gemini-2.0-flash`.
* `--log-level <LEVEL>`: (Optional) Set the console logging level. Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Defaults to `INFO`.

## Output Files

Whether run via the web server or command line, output files are generated in the `~/pdf_to_civiform/output-json/` directory.

The "PREFIX" in the filenames refers to the original PDF filename (sanitized and shortened, without the '.pdf' extension). The "MODEL" refers to the specific Gemini model used (e.g., `gemini-2.0-flash`).

**Main Output:**

* `PREFIX-civiform-MODEL.json`: The final JSON output ready to be imported into CiviForm. This is generated after successful completion of all steps.

**Intermediate Files (useful for debugging):**

* `PREFIX-pdf-extract-MODEL.json`: (Saved only if log level is DEBUG) Raw JSON extracted by the LLM in the first step.
* `PREFIX-formatted-MODEL.json`: The JSON output after applying formatting rules.
* `PREFIX-post-processed-MODEL.json`: (Saved only if log level is DEBUG) Raw JSON output from the LLM during the post-processing/collating step.
* `PREFIX-post-processed-formatted-MODEL.json`: The JSON output from post processing after applying formatting rules. This is the structure passed to the CiviForm json conversion.

## Importing to CiviForm

Import the generated CiviForm JSON into CiviForm using the "[Import program" flow](https://docs.civiform.us/user-manual/civiform-admin-guide/program-migration#importing-a-program):

1.  Log in as a CiviForm admin.
2.  Navigate to the Programs page.
3.  Click the "Import existing program" link.
4.  Paste the content of the `PREFIX-civiform-MODEL.json` file into the text area.
5.  Follow the on-screen instructions to complete the import.