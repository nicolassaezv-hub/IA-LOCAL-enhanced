# ASTRA — AI Local Modular System

A comprehensive local AI assistant and Forex analytics platform built in Python. It wraps OpenAI's API with dozens of specialized tools: document processing, web scraping, audio/video, machine learning (PyTorch, TensorFlow, Keras), security utilities, and an integrated Forex ML prediction pipeline.

## How to Run

Start via the **"Start application"** workflow (console output). The app opens an interactive CLI prompt `Tú:` where you type commands in Spanish or English.

## Requirements

**You must add your OpenAI API key** as an environment secret named `OPENAI_API_KEY` — the app uses GPT-3.5-turbo for the AI assistant and falls back to it for unrecognized commands.

## Key Commands

| Command | What it does |
|---|---|
| `analiza forex` | Forex market analysis |
| `estado pc` | Show CPU / RAM usage |
| `lee pdf <path>` | Read a PDF file |
| `extrae web <url>` | Scrape a webpage |
| `traducir <text>` | Translate text |
| `torch demo` | PyTorch tensor demo |
| `tensorflow demo` | TensorFlow demo |
| `sklearn demo` | Scikit-learn demo |
| `hash pass <text>` | Bcrypt hash a password |
| `crear jwt` | Generate a JWT token |
| `integral` | Symbolic integration demo |
| `salir` / `exit` | Quit |

## Linux Adaptations Made

- **Redis**: Optional (used for key-value memory). Not required to run.
- **PyQt5 GUI**: Available but headless in server mode.
- **Audio I/O**: SpeechRecognition / pyttsx3 require microphone/speakers (not available in hosted env).
- **Windows-only packages**: `keyboard`, `mouse`, `pywin32`, `Kivy` — gracefully skipped.
- **matplotlib**: Set to non-interactive `Agg` backend.

## User Preferences

- Project is a Python CLI, not a web app.
