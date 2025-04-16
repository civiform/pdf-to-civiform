# Dockerfile (~/pdf-to-civiform/src/pdf_to_json/Dockerfile)
FROM python:3.13-slim-bookworm

ARG USER_NAME=cf-user
ARG GROUP_NAME=cf-group
ARG USER_HOME=/home/${USER_NAME}
# WORK_DIR will be inside the user's home
ARG WORK_DIR=${USER_HOME}/pdf_to_civiform
ARG APP_DIR=${WORK_DIR}/app

# Create group, user, and user's home directory
RUN groupadd --system ${GROUP_NAME} && \
    useradd --system --gid ${GROUP_NAME} --create-home --home-dir ${USER_HOME} ${USER_NAME}

# Create the workdir, app dir, uploads, cache within user's home
# Set ownership of the user's entire home dir structure early
RUN mkdir -p ${APP_DIR} ${WORK_DIR}/uploads ${WORK_DIR}/python_cache && \
    chown -R ${USER_NAME}:${GROUP_NAME} ${USER_HOME}

# Set the working directory (Gunicorn will run from here)
WORKDIR ${WORK_DIR}

# Copy the dependencies file into the app directory
# Need to switch user temporarily or adjust permissions/ownership later
# Let's copy as root then chown later
COPY python_dependencies.txt ${APP_DIR}/

# Install dependencies
RUN pip install --no-cache-dir -r ${APP_DIR}/python_dependencies.txt

# Copy the application code into the app directory (relative to WORKDIR doesn't work here)
COPY . ${APP_DIR}/

## TODO - get Gemini API key for demo env
# --- WARNING: Embedding API key in image is insecure ---
# Copy the API key from the build context *root* to the WORKDIR
# COPY google_api_key .

# Change ownership of copied items (deps file, app code, api key)
#RUN chown -R ${USER_NAME}:${GROUP_NAME} ${APP_DIR} ${WORK_DIR}/google_api_key

# Add the app directory to the Python path
ENV PYTHONPATH=${APP_DIR}

# Use port 7000
ENV PORT=7000
ENV PYTHONUNBUFFERED=1

# Switch to the non-root user
USER ${USER_NAME}

# Expose the port (runs as cf-user)
EXPOSE 7000

# Define the command to run Gunicorn (runs as cf-user from WORKDIR)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --timeout 900 pdf_to_civiform_gemini:app"]