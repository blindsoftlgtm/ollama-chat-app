# Olama-Chat

## What is Ollama-Chat?

Ollama-chat is a client for Llama, which is a program for running local LLMs (Large Language Models) on your computer. It provides an easy-to-use interface to interact with models powered by the Ollama API.

## Installation

This program is written in Python and uses the `requests` library for connecting to the Ollama API.

To start, run the following command:

```bash
ollama serve
```

## Create the Virtual Environment

First, you need to create a virtual environment to collect all the required modules. Run the following command:

```bash
python3 -m venv venv
```

> Replace `venv` at the end with your preferred name for the virtual environment.

Then, assuming you have cloned this repository and created the virtual environment in the project folder, navigate into the project directory:

```bash
cd ollama_chat_app
```

Now, activate the virtual environment using one of the following commands:

- **Windows** (may not work on all systems):
  ```bash
  venv\Scripts\activate
  ```

- **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

You are now inside the virtual environment.

## Installing Dependencies

Let's install the required dependencies. Run the following command:

```bash
pip install -r requirements.txt
```

Wait for the installation to complete before proceeding.

## Running the Script

Now, let's run the Python script:

```bash
python3 ollama_chat.py
```

Python will launch, and you can start using the client.

## Contributing

This repository is licensed under the MIT License, but you are welcome to make changes and contribute at any time. 

This project is maintained by Blindsoft, a team dedicated to creating accessible software for the blind and visually impaired. Contributions are encouraged to help improve accessibility and functionality for all users.
