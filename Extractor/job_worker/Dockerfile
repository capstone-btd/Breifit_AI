# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Add the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the cache which is useful for keeping image size down
# -r requirements.txt: Installs packages from the given requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Run run_full_pipeline.py when the container launches
CMD ["python", "run_full_pipeline.py"] 