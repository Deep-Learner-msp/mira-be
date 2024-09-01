# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Expose port 8000 for the app
EXPOSE 8000

# Set environment variables
ENV PORT=8000

# Run the application
CMD ["chainlit", "run", "mira.py", "--port", "8000"]
