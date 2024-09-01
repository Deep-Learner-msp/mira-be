# Use an official Python runtime based on Ubuntu as a parent image
FROM ubuntu:20.04

# Install Python and pip
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get install -y python3.11 python3.11-distutils python3.11-venv curl && \
    rm -rf /var/lib/apt/lists/*

# Set Python3.11 as the default python
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Set the working directory in the container
WORKDIR /app
# Copy the requirements.txt file into the container
COPY requirements.txt /app/

# Set EULA acceptance
ENV ACCEPT_EULA=Y

# Add Microsoft repository and install packages
RUN curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc && \
    curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | tee /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 unixodbc-dev && \
    rm -rf /var/lib/apt/lists/*

# Add SQL Server tools to PATH
ENV PATH="$PATH:/opt/mssql-tools18/bin"

# Install required packages
RUN apt-get update && apt-get install -y python3-html5lib

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run uvicorn when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
