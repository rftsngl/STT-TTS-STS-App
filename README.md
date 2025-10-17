# 🎙️ TR Speech Stack - Advanced Speech Processing Service

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119.0-green)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/rftsngl/STT-TTS-STS-App)

A production-ready FastAPI-based speech processing service providing enterprise-grade Speech-to-Text (STT), Text-to-Speech (TTS), voice management, and audio processing capabilities with comprehensive security, monitoring, and resilience patterns.

---

## ✨ Key Features

### 🎯 Core Speech Processing
- **Speech-to-Text (STT)** - Convert audio to text using Faster-Whisper
  - Multi-language support (Turkish, English, etc.)
  - Word-level and segment-level timestamps
  - Voice Activity Detection (VAD)
  - Noise suppression
  - Max duration: 15 minutes

- **Text-to-Speech (TTS)** - Generate natural speech from text via ElevenLabs
  - Multi-language support
  - Multiple voice options
  - Streaming support
  - Multiple output formats (MP3, PCM, WAV)

- **Chained Operations** - Combine STT + TTS in single request
  - Audio-to-Audio transformation
  - Real-time processing

### 🎤 Voice Management
- Voice listing and browsing
- Custom voice aliases
- Voice cloning (IVC - Instant Voice Cloning)
- Voice metadata and descriptions

### 🔊 Audio Processing
- Noise reduction (Spectral or RNNoise)
- Voice isolation and enhancement
- Audio format conversion
- Automatic normalization to 16kHz mono PCM

### 🛡️ Enterprise Security
- **API Key Authentication** - X-API-Key header validation
- **Admin Authorization** - X-Admin-Key for privileged operations
- **Rate Limiting** - Global (300 RPM) and per-IP (150 RPM) limits
- **Body Size Limits** - 20MB upload, 25MB body
- **Constant-time Comparison** - Timing attack resistant

### 📊 Monitoring & Diagnostics
- Real-time health checks
- Comprehensive metrics collection (JSON Lines format)
- Error tracking and analysis
- Performance monitoring
- System diagnostics API

### 🔄 Resilience Patterns
- **Circuit Breaker** - Automatic failure detection and recovery
- **Exponential Backoff** - Intelligent retry with jitter
- **Watchdog Timeouts** - Operation timeout protection
- **Graceful Degradation** - Fallback mechanisms

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- FFmpeg (for audio processing)
- CUDA 11.8+ (optional, for GPU acceleration)
- ElevenLabs API key (for TTS)

### Installation

```bash
# Clone repository
git clone https://github.com/rftsngl/STT-TTS-STS-App.git
cd STT-TTS-STS-App

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Running the Service

```bash
# Development mode with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Access Services

- **API Documentation:** http://localhost:8000/docs
- **OpenAPI Schema:** http://localhost:8000/openapi.json
- **Admin Dashboard:** http://localhost:8000/ui
- **Health Check:** http://localhost:8000/health

---

## 📡 API Endpoints

### Core Processing (3 endpoints)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/stt` | POST | Speech to Text |
| `/tts` | POST | Text to Speech |
| `/speak` | POST | Chained STT+TTS |

### Voice Management (4 endpoints)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voices` | GET | List available voices |
| `/voices/aliases` | GET/POST | Manage voice aliases |
| `/voices/aliases/{alias}` | DELETE | Delete alias |
| `/providers/elevenlabs/ivc` | POST | Voice cloning |

### Audio Processing (1 endpoint)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/audio/isolation` | POST | Audio enhancement |

### Diagnostics (5 endpoints)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | System status |
| `/diag/routes` | GET | API listing |
| `/diag/capabilities` | GET | Feature list |
| `/diag/metrics/summary` | GET | Metrics |
| `/diag/errors/summary` | GET | Error stats |

### Admin (6 endpoints)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/terms` | GET/POST/PUT/DELETE | Term management |
| `/terms/import` | POST | Bulk import |
| `/ui` | GET | Admin dashboard |

**Full API Documentation:** See [MOBIL_API_DOKUMANTASYONU.md](MOBIL_API_DOKUMANTASYONU.md)

---

## ⚙️ Configuration

### Environment Variables (50+)

**Device & Performance:**
```env
DEVICE=auto|cuda|cpu              # GPU/CPU selection
BIND_HOST=0.0.0.0                 # Network binding
PORT=8000                         # Service port
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
```

**STT Configuration:**
```env
DEFAULT_LANGUAGE=tr               # Default language
DEFAULT_TIMESTAMPS=segments|words # Timestamp granularity
MAX_DURATION_SECONDS=900          # Max audio length
VAD_AGGRESSIVENESS=1-3            # Voice activity detection
NOISE_SUPPRESSOR=off|spectral|rnnoise
```

**TTS Configuration:**
```env
XI_API_KEY=sk_...                 # ElevenLabs API key
ELEVEN_MODEL_ID=eleven_flash_v2_5
ELEVEN_OUTPUT_FORMAT=mp3_22050_32
```

**Security:**
```env
ENABLE_SECURITY=true              # Enable API key protection
API_KEY=your-secure-key           # API key
ADMIN_KEY=your-admin-key          # Admin key
RATE_LIMIT_GLOBAL_RPM=300         # Global rate limit
RATE_LIMIT_IP_RPM=150             # Per-IP rate limit
```

**Resilience:**
```env
BACKOFF_RETRIES=3                 # Retry attempts
BACKOFF_BASE_MS=250               # Base retry delay
HTTP_READ_TIMEOUT_SEC=30          # Read timeout
HTTP_WRITE_TIMEOUT_SEC=60         # Write timeout
```

See [COMPREHENSIVE_BACKEND_REPORT.md](COMPREHENSIVE_BACKEND_REPORT.md) for complete configuration reference.

---

## 🔐 Security

### Authentication
- API key validation via `X-API-Key` header
- Admin operations via `X-Admin-Key` header
- Constant-time comparison (timing attack resistant)

### Rate Limiting
- Global: 300 requests/minute
- Per-IP: 150 requests/minute
- Burst factor: 2.0 (temporary spikes allowed)
- Admin bypass available

### Request Validation
- Body size limits (20MB upload, 25MB body)
- Content-type validation
- Input sanitization

### Best Practices
1. Enable `ENABLE_SECURITY=true` in production
2. Use strong, randomly generated API keys
3. Rotate keys regularly
4. Monitor rate limit violations
5. Enable HTTPS/SSL
6. Use firewall rules
7. Keep dependencies updated

---

## 📊 Performance

### Targets
| Operation | Target | Typical |
|-----------|--------|---------|
| STT Processing | 120ms | ~120ms |
| TTS Processing | 120ms | ~120ms |
| Total Operation | 250ms | ~245ms |
| API Response | <100ms | ~50ms |

### Optimization Tips
- Use GPU (CUDA) for STT acceleration
- Enable caching for repeated operations
- Use appropriate audio formats
- Monitor metrics for bottlenecks
- Scale horizontally with load balancer

---

## 🧪 Testing

### Run Tests
```bash
pytest
```

### Test Coverage
- Health endpoint tests
- STT functionality tests
- TTS functionality tests
- Chained operation tests
- Security and rate limiting tests
- Metrics collection tests
- Resilience pattern tests

### Manual Testing
```bash
# Health check
curl http://localhost:8000/health

# STT example
curl -X POST http://localhost:8000/stt \
  -H "X-API-Key: your-api-key" \
  -F "audio_file=@test.wav" \
  -F "language=tr"

# TTS example
curl -X POST http://localhost:8000/tts \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba","voice_id":"voice-123","language":"tr"}'
```

---

## 📦 Dependencies

### Core Framework
- **FastAPI** 0.119.0 - Web framework
- **Uvicorn** 0.37.0 - ASGI server
- **Pydantic** 2.12.0 - Data validation

### ML/Audio
- **Faster-Whisper** 1.2.0 - STT model
- **PyTorch** 2.5.1 - Deep learning
- **TorchAudio** 2.5.1 - Audio processing
- **SoundFile** 0.13.1 - Audio I/O
- **PyDub** 0.25.1 - Audio manipulation
- **WebRTC VAD** 2.0.10 - Voice detection
- **NoiseReduce** 3.0.3 - Noise suppression

### External Services
- **ElevenLabs** 2.17.0 - TTS provider
- **HTTPX** 0.28.1 - HTTP client

### Utilities
- **Loguru** 0.7.3 - Logging
- **python-dotenv** 1.1.1 - Environment config

See [requirements.txt](requirements.txt) for complete list.

---

## 🚢 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist
- [ ] Set `ENABLE_SECURITY=true`
- [ ] Configure strong API keys
- [ ] Set `BIND_HOST=0.0.0.0`
- [ ] Configure rate limiting
- [ ] Set up log rotation
- [ ] Configure ElevenLabs API key
- [ ] Enable HTTPS/SSL
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Test disaster recovery

### Scaling
- Stateless design (horizontal scaling ready)
- Load balancer recommended
- Metrics aggregation across instances
- Per-IP rate limiting (not global)

---

## 📚 Documentation

- **[COMPREHENSIVE_BACKEND_REPORT.md](COMPREHENSIVE_BACKEND_REPORT.md)** - Complete backend analysis
- **[MOBILE_INTEGRATION_GUIDE.md](MOBILE_INTEGRATION_GUIDE.md)** - Mobile app integration
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Project overview
- **[MOBIL_API_DOKUMANTASYONU.md](MOBIL_API_DOKUMANTASYONU.md)** - API documentation (Turkish)

Coming soon...

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements.txt pytest pytest-cov

# Run tests
pytest

# Check coverage
pytest --cov=app
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support & Contact

- **Issues:** [GitHub Issues](https://github.com/rftsngl/STT-TTS-STS-App/issues)

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - STT model
- [ElevenLabs](https://elevenlabs.io/) - TTS provider
- [PyTorch](https://pytorch.org/) - Deep learning framework

---

**Made with ❤️ by [Rıfat Sinanoglu](https://github.com/rftsngl)**

**Last Updated:** 2025-10-17  
**Version:** 0.1.0  
**Status:** ❇️ Ongoing

