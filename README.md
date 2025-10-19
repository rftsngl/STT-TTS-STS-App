# 🎙️ STT-TTS-STS Application

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119.0-green)](https://fastapi.tiangolo.com/)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-2.17.0-purple)](https://elevenlabs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-ready FastAPI backend providing **Speech-to-Text (STT)** and **Text-to-Speech (TTS)** services powered by **ElevenLabs**. Features a Turkish language admin UI for easy configuration and management.

> **🌍 Language:** Admin UI is in Turkish (Türkçe)
> **🔑 Provider:** ElevenLabs (STT & TTS)
> **🗄️ Storage:** SQLite database with encrypted API key storage

---

## ✨ Features

### 🎯 Core Capabilities
- **Speech-to-Text (STT)** - Transcribe audio to text using ElevenLabs
  - Multi-language support (Turkish, English, and more)
  - Word-level and segment-level timestamps
  - Supports WAV, MP3, M4A, FLAC formats
  - Maximum duration: 15 minutes

- **Text-to-Speech (TTS)** - Generate natural speech using ElevenLabs
  - Multi-language support
  - Multiple voice options
  - Streaming support
  - Multiple output formats (MP3, PCM, WAV)

- **Chained Operations** - Combine STT + TTS in a single request
  - Audio-to-audio transformation
  - Voice conversion

### 🎤 Voice Management
- List available voices
- Custom voice aliases
- Voice cloning (IVC - Instant Voice Cloning)
- Voice metadata and descriptions

### 🔊 Audio Processing
- Noise reduction (Spectral or RNNoise)
- Voice isolation and enhancement
- Audio format conversion
- Automatic normalization

### 🛡️ Security
- **Database-backed API Key Storage** - Encrypted with Fernet (AES-256)
- **API Key Authentication** - X-API-Key or X-ElevenLabs-Key headers
- **Rate Limiting** - Configurable global and per-IP limits
- **Request Validation** - Body size limits and content-type validation

### 📊 Monitoring
- Real-time health checks
- Comprehensive metrics collection
- Error tracking and analysis
- System diagnostics API

### �️ Admin UI
- **Turkish language interface** at `/ui`
- Easy ElevenLabs API key configuration
- Voice management
- System status monitoring
- No initial setup screen - use topbar form

---

## � Prerequisites

Before you begin, ensure you have:

- **Python 3.11 or higher** ([Download](https://www.python.org/downloads/))
- **pip** (Python package manager, included with Python)
- **ElevenLabs API Key** ([Get one here](https://elevenlabs.io/app/settings/api-keys))
- **FFmpeg** (optional, for advanced audio processing)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/rftsngl/STT-TTS-STS-App.git
cd STT-TTS-STS-App
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** The `requirements.txt` includes optional dependencies (PyTorch, Faster-Whisper) that are not actively used. Only ElevenLabs is currently supported for STT/TTS.

### 4. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env
```

**Edit `.env` file and set the following:**

1. **Generate an encryption key:**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Update `.env` with the generated key:**
   ```env
   ENCRYPTION_KEY=your-generated-key-here
   ```

3. **Set bind host (to allow connections from mobile app):**
   ```env
   BIND_HOST=0.0.0.0
   ```

**⚠️ Important:**
- Do NOT set `XI_API_KEY` in `.env` file
- API keys are managed through the admin UI and stored in the database
- The `ENCRYPTION_KEY` must remain the same across restarts to decrypt stored keys

### 5. Start the Server

```bash
# Development mode (with auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. Configure ElevenLabs API Key

1. Open your browser and navigate to: **http://localhost:8000/ui**
2. In the topbar, find the **"ElevenLabs API Key"** input field
3. Enter your ElevenLabs API key (starts with `sk_...`)
4. Click **"ElevenLabs Key Kaydet"** (Save ElevenLabs Key)
5. You should see a success message

**✅ Your application is now ready to use!**

---

## 📡 API Endpoints

### Access Points

- **Interactive API Documentation:** http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs:** http://localhost:8000/redoc (ReDoc)
- **Admin Dashboard:** http://localhost:8000/ui (Turkish UI)
- **Health Check:** http://localhost:8000/health

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stt` | POST | Speech-to-Text transcription |
| `/tts` | POST | Text-to-Speech synthesis |
| `/speak` | POST | Chained STT+TTS operation |
| `/voices` | GET | List available voices |
| `/health` | GET | System health status |

### Example: Speech-to-Text

```bash
curl -X POST http://localhost:8000/stt \
  -H "X-ElevenLabs-Key: sk_your_api_key_here" \
  -F "audio_file=@audio.wav" \
  -F "language=tr" \
  -F "timestamps=segments"
```

### Example: Text-to-Speech

```bash
curl -X POST http://localhost:8000/tts \
  -H "X-ElevenLabs-Key: sk_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Merhaba, nasılsınız?",
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "language": "tr"
  }' \
  --output speech.mp3
```

**📚 Full API Documentation:** Visit http://localhost:8000/docs after starting the server

---

## ⚙️ Configuration

### Environment Variables

The application is configured via the `.env` file. Copy `.env.example` to `.env` and customize as needed.

**Essential Settings:**

```env
# Database & Encryption (REQUIRED)
DATABASE_PATH=./data/speech_app.db
ENCRYPTION_KEY=your-generated-encryption-key-here

# Server Configuration
BIND_HOST=0.0.0.0                 # Allow external connections
PORT=8000                         # Server port
LOG_LEVEL=INFO                    # Logging level

# ElevenLabs Configuration
ELEVEN_MODEL_ID=eleven_flash_v2_5
ELEVEN_OUTPUT_FORMAT=mp3_22050_32
ELEVEN_TTS_LANGUAGE=tr

# STT Provider (ElevenLabs only)
STT_PROVIDER=elevenlabs
STT_FALLBACK_ENABLED=0

# Security
ENABLE_SECURITY=1
API_KEY=changeme                  # Internal API key
RATE_LIMIT_GLOBAL_RPM=180
RATE_LIMIT_IP_RPM=90
```

**⚠️ Important Notes:**

1. **ENCRYPTION_KEY** - Must be set and remain constant across restarts
   - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - Changing this key will make existing stored API keys unreadable

2. **XI_API_KEY** - Do NOT set this in `.env`
   - API keys are managed through the admin UI at `/ui`
   - Keys are stored encrypted in the database

3. **BIND_HOST** - Set to `0.0.0.0` to allow mobile app connections
   - Use `127.0.0.1` for localhost-only access

**📄 See `.env.example` for all available configuration options**

---

## � Project Structure

```
STT-TTS-STS-App/
├── app/                      # Main application code
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database and encryption
│   ├── stt.py               # Speech-to-Text endpoint
│   ├── tts_cloud.py         # Text-to-Speech endpoint
│   ├── chain_http.py        # Chained STT+TTS endpoint
│   ├── voices_api.py        # Voice management
│   ├── health.py            # Health check endpoint
│   ├── ui_admin.py          # Admin UI endpoints
│   ├── voice_utils.py       # ElevenLabs provider utilities
│   ├── stt_provider.py      # STT provider management
│   ├── security/            # Security modules
│   │   └── api_key.py       # API key authentication
│   └── templates/           # HTML templates
│       └── ui_admin.html    # Turkish admin UI
├── providers/               # External service providers
│   └── elevenlabs_tts.py    # ElevenLabs integration
├── data/                    # Data directory
│   ├── speech_app.db        # SQLite database (excluded from git)
│   ├── terms.json           # Term replacements
│   └── voice_aliases.json   # Voice aliases
├── tests/                   # Test files
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── DEPLOYMENT_GUIDE.md      # Deployment instructions
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. **"Invalid encryption key" error**

**Problem:** The `ENCRYPTION_KEY` in `.env` is invalid or missing.

**Solution:**
```bash
# Generate a new encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add it to .env
ENCRYPTION_KEY=your-generated-key-here
```

#### 2. **"ElevenLabs API key not configured" error**

**Problem:** No API key has been saved in the database.

**Solution:**
1. Open http://localhost:8000/ui
2. Enter your ElevenLabs API key in the topbar
3. Click "ElevenLabs Key Kaydet"

#### 3. **Cannot connect from mobile app**

**Problem:** Server is not accessible from the mobile device.

**Solution:**
- Ensure `BIND_HOST=0.0.0.0` in `.env`
- Check firewall settings
- Verify mobile device is on the same network
- Use your computer's local IP address (not localhost)

#### 4. **"Database is locked" error**

**Problem:** Multiple processes trying to access the database.

**Solution:**
- Stop all running instances of the application
- Delete `data/speech_app.db-journal` if it exists
- Restart the application

#### 5. **API key becomes invalid after restart**

**Problem:** The `ENCRYPTION_KEY` changed between restarts.

**Solution:**
- Ensure `ENCRYPTION_KEY` is set in `.env` and never changes
- If you lost the key, you'll need to re-enter your ElevenLabs API key in the UI

---

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_health.py
```

### Test Coverage

The project includes tests for:
- Health endpoint and system status
- API key storage and encryption
- STT functionality
- TTS functionality
- Security and authentication
- Metrics collection

---

## 🚀 Deployment

For production deployment, see the comprehensive **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** which covers:

- Local development setup
- Cloud deployment (Heroku, AWS, Azure, Google Cloud)
- Docker deployment
- Mobile app configuration
- Security best practices
- Troubleshooting

---

## 📱 Mobile Application

A React Native mobile application (Voice Studio) is included in the `ui/SpeechApp` directory, providing a modern mobile interface for STT and TTS services.

### 📲 Connecting the Mobile App to the Server

#### **Step 1: Start the Backend Server**

You need to start the backend server on your computer:

```powershell
# Navigate to the project folder
cd /path/to/STT-TTS-STS-App

# Start the server (0.0.0.0 listens on all network interfaces)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

When the server starts, you will see output like this:

```text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

#### **Step 2: Determine Your Computer's IP Address**

To connect your mobile device to the server, you need to find your computer's local network IP address.

**Windows:**

```powershell
ipconfig | Select-String -Pattern "IPv4"
```

**Linux/Mac:**

```bash
ifconfig | grep "inet "
# or
ip addr show
```

You will use one of the IP addresses shown in the output (e.g., `192.168.1.100`, `10.0.0.50`, etc.)

**Which IP should you use?**

- If your mobile device is **on the same Wi-Fi network**: Use your main network IP (typically `192.168.x.x` or `10.x.x.x`)
- If your mobile device is **connected to your computer's hotspot**: Use the hotspot IP (typically `192.168.137.1`)

---

#### **Step 3: Configure the Mobile App Settings**

1. Open the **Voice Studio** app
2. Navigate to the **⚙️ Settings** tab from the bottom menu
3. Enter the following information:

##### **A) ElevenLabs API Key**

- Enter your ElevenLabs API key (e.g., `sk_...`)
- You can get this key from https://elevenlabs.io/app/settings/api-keys

##### **B) Server URL**

- **If using Android emulator**: `http://10.0.2.2:8000` (special address for Android emulator)
- **If using iOS Simulator**: `http://localhost:8000`
- **If using a physical device**: `http://YOUR_COMPUTER_IP:8000`
  - Example: `http://192.168.1.100:8000`
  - Example: `http://10.0.0.50:8000`

4. Tap the **"Save"** button

---

#### **Step 4: Test the Connection**

1. Go to the **Home** tab
2. Tap the **"Refresh"** button or pull down to refresh (pull-to-refresh)
3. If the connection is successful:
   - ✅ **Status**: Will show "healthy"
   - ✅ **Features**: Active features will be listed
   - ✅ **Metrics**: Statistics will be displayed

4. Go to the **Voices** tab
   - The list of ElevenLabs voices will load
   - If you see voices, the connection is successful! 🎉

---

#### **Step 5: Try the Features**

##### **🎤 Speech-to-Text (STT)**

1. Go to the **STT** tab
2. Select an audio file or record audio
3. Tap the **"Transcribe"** button
4. The transcript result will appear

##### **🔊 Text-to-Speech (TTS)**

1. Go to the **TTS** tab
2. Enter some text (e.g., "Hello world")
3. Select a voice
4. Tap the **"Generate Speech"** button
5. The audio file will be generated and you can play it

---

## 📦 Dependencies

### Core Framework

- **FastAPI** 0.119.0 - Modern web framework
- **Uvicorn** 0.37.0 - ASGI server
- **Pydantic** 2.12.0 - Data validation

### Audio Processing

- **SoundFile** 0.13.1 - Audio I/O
- **PyDub** 0.25.1 - Audio manipulation
- **WebRTC VAD** 2.0.10 - Voice activity detection
- **NoiseReduce** 3.0.3 - Noise suppression

### External Services

- **ElevenLabs** 2.17.0 - STT & TTS provider
- **HTTPX** 0.28.1 - HTTP client

### Database & Security

- **Cryptography** 42.0.5 - Fernet encryption for API keys

### Utilities

- **Loguru** 0.7.3 - Logging
- **python-dotenv** 1.1.1 - Environment configuration
- **psutil** 6.1.0 - System monitoring

### Optional Dependencies

The following are included in `requirements.txt` but are **not actively used**:
- **PyTorch** 2.5.1 - (for Faster-Whisper, which is disabled)
- **Faster-Whisper** 1.2.0 - (disabled, ElevenLabs is used instead)

**📄 See [requirements.txt](requirements.txt) for the complete list**

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov

# Run tests
pytest

# Check coverage
pytest --cov=app --cov-report=html
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/rftsngl/STT-TTS-STS-App/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rftsngl/STT-TTS-STS-App/discussions)

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- [ElevenLabs](https://elevenlabs.io/) - High-quality STT & TTS services
- [Cryptography](https://cryptography.io/) - Secure encryption library

---

**Made with ❤️ for the developer community**

**Last Updated:** 2025-10-19
**Version:** 1.0.0
**Status:** ✅ Production Ready
