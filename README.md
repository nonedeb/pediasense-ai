# PediaSense AI - Import Users Module (Production-Ready Starter)

## Features
- CSV upload for students or faculty
- Preview before confirm
- Validation for required fields
- Duplicate email prevention
- Saves valid rows to database
- Import logs
- Cancel pending import safely

## Student CSV columns
name,section,program,contact_number,email

## Faculty CSV columns
name,email,specialization,post_nominals,contact_number

## Run locally
```bash
pip install -r requirements.txt
python app.py
```

## Deploy on Render
Start command:
```bash
gunicorn app:app
```
