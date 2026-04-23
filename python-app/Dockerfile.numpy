# numpy-alpine: with numpy dependency on alpine base.
FROM python:3.13-alpine

WORKDIR /app

COPY requirements-numpy.txt .
RUN pip install --no-cache-dir -r requirements-numpy.txt

COPY spaceship/ ./spaceship/
COPY build/ ./build/

EXPOSE 8000
CMD ["uvicorn", "spaceship.main:app", "--host", "0.0.0.0", "--port", "8000"]
