# Step 1: Use a lightweight Python image
FROM python:3.9-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Copy your application files into the container
COPY . /app

# Step 4: Install your dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Expose the port your app runs on
EXPOSE 8080

# Step 6: Command to run your app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
