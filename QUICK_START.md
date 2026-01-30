# Quick Start Guide

## Step 1: Run Setup Script

```bash
cd path/to/med-EVE   # or wherever you cloned the repo
./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Set everything up

## Step 2: Activate Virtual Environment

Every time you open a new terminal:

```bash
cd path/to/med-EVE   # same as above
source venv/bin/activate
```

You should see `(venv)` in your prompt.

## Step 3: Test in Lite Mode (No Model Needed)

```bash
make demo
```

This runs without the model - perfect for testing the setup!

## Step 4: Set Up Model Mode (Optional)

If you want to use the actual MedGemma model:

### 4a. Login to HuggingFace

```bash
huggingface-cli login
```

Get your token from: https://huggingface.co/settings/tokens

### 4b. Accept Model Terms

Visit: https://huggingface.co/google/medgemma-4b-it
Click "Agree and access repository"

### 4c. Download Model

```bash
python scripts/download_model.py
```

This downloads ~8GB and takes 10-30 minutes.

### 4d. Run with Model

```bash
export MODE=model
make demo
```

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run demo (lite mode)
make demo

# Run demo (model mode)
export MODE=model
make demo

# Run backend only
make run

# Run tests
make verify

# Stop servers
make stop
```

## Troubleshooting

**"pip: command not found"**
- Use `pip3` instead, or activate venv first: `source venv/bin/activate`

**"Permission denied"**
- Don't use `sudo` with pip in virtual environment
- Make sure venv is activated

**Import errors**
- Activate virtual environment: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

## Full Documentation

See `SETUP_COMPLETE_GUIDE.md` for detailed instructions.
