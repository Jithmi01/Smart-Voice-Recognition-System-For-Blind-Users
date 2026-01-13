"""
Voice Recognition API - Main Application
Backend server for voice-based speaker identification
"""

from flask import Flask, jsonify
from flask_cors import CORS
import logging
import sys
import os
from dotenv import load_dotenv
from datetime import datetime
import torch


# Import configurations and services
from config import Config
from services.voice_service import VoiceRecognitionService
from utils.audio_processor import AudioProcessor
from routes.voice_routes import init_voice_routes

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
Config.init_app(app)
CORS(app)  # Enable CORS for mobile app communication

# Global services (initialized once at startup)
voice_service = None
audio_processor = None


@app.route('/')
def index():
    """API information endpoint"""
    return jsonify({
        "status": "running",
        "message": "🎤 Voice Recognition API",
        "version": "1.0.0",
        "model": "SpeechBrain ECAPA-TDNN",
        "endpoints": {
            "register": "POST /api/voice/register - Register new user with voice samples",
            "identify": "POST /api/voice/identify - Identify speaker from voice",
            "verify": "POST /api/voice/verify - Verify speaker identity",
            "users": "GET /api/voice/users - Get all registered users",
            "delete_user": "DELETE /api/voice/users/<name> - Delete user by name",
            "health": "GET /health - Check system health"
        },
        "documentation": {
            "register": {
                "method": "POST",
                "form_data": {
                    "name": "User's name (string)",
                    "audio_files": "1-5 audio files (WAV/MP3/M4A)"
                }
            },
            "identify": {
                "method": "POST",
                "form_data": {
                    "audio_file": "Audio file to identify (WAV/MP3/M4A)",
                    "threshold": "Similarity threshold (optional, default: 0.65)"
                }
            }
        }
    })


@app.route('/health')
def health():
    """
    Health check endpoint with detailed system status
    Useful for monitoring and debugging
    """
    try:
        # Import MongoDB client here to check connection
        from pymongo import MongoClient
        
        # Test MongoDB connection
        mongo_client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=2000)
        mongo_client.admin.command('ping')
        db = mongo_client[Config.DATABASE_NAME]
        user_count = db['users'].count_documents({})
        mongo_status = "connected"
        mongo_client.close()
        
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        user_count = 0
        mongo_status = "disconnected"
    
    # Check voice service
    voice_status = "loaded" if voice_service is not None else "not loaded"
    
    # Check audio processor
    audio_status = "ready" if audio_processor is not None else "not ready"
    
    # Overall health
    is_healthy = mongo_status == "connected" and voice_status == "loaded"
    
    return jsonify({
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "mongodb": {
                "status": mongo_status,
                "database": Config.DATABASE_NAME,
                "registered_users": user_count
            },
            "voice_recognition": {
                "status": voice_status,
                "model": Config.MODEL_NAME,
                "device": "GPU" if torch.cuda.is_available() else "CPU"
            },
            "audio_processor": {
                "status": audio_status,
                "target_sr": "16000 Hz"
            }
        },
        "configuration": {
            "similarity_threshold": Config.SIMILARITY_THRESHOLD,
            "min_audio_duration": f"{Config.MIN_AUDIO_DURATION}s",
            "max_audio_duration": f"{Config.MAX_AUDIO_DURATION}s",
            "allowed_formats": list(Config.ALLOWED_EXTENSIONS)
        }
    }), 200 if is_healthy else 503


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "message": "Check /health for available endpoints"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": "Check server logs for details"
    }), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors"""
    return jsonify({
        "success": False,
        "error": "File too large",
        "message": f"Maximum file size: {Config.MAX_CONTENT_LENGTH / 1024 / 1024}MB"
    }), 413


def initialize_services():
    """Initialize all services and dependencies"""
    global voice_service, audio_processor
    
    try:
        logger.info("")
        logger.info("=" * 70)
        logger.info("🚀 INITIALIZING VOICE RECOGNITION SYSTEM")
        logger.info("=" * 70)
        
        # Verify .env file exists
        if not os.path.exists('.env'):
            logger.error("❌ .env file not found!")
            logger.error("💡 Create .env file with MONGODB_URI and other settings")
            return False
        
        # Verify MongoDB URI is set
        if not Config.MONGODB_URI:
            logger.error("❌ MONGODB_URI not set in .env file!")
            logger.error("💡 Add MONGODB_URI to your .env file")
            return False
        
        logger.info(f"✅ Configuration loaded from .env")
        logger.info(f"📊 Database: {Config.DATABASE_NAME}")
        
        # Test MongoDB connection
        logger.info("")
        logger.info("📦 Testing MongoDB connection...")
        from pymongo import MongoClient
        
        try:
            mongo_client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command('ping')
            db = mongo_client[Config.DATABASE_NAME]
            user_count = db['users'].count_documents({})
            
            logger.info(f"✅ MongoDB connected successfully!")
            logger.info(f"✅ Database: {Config.DATABASE_NAME}")
            logger.info(f"✅ Registered users: {user_count}")
            
            mongo_client.close()
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            logger.error("💡 Check your MONGODB_URI in .env file")
            logger.error("💡 Verify IP whitelist in MongoDB Atlas")
            return False
        
        # Initialize audio processor
        logger.info("")
        logger.info("🎵 Initializing audio processor...")
        audio_processor = AudioProcessor(target_sr=16000)
        logger.info("✅ Audio processor ready")
        
        # Initialize voice recognition service
        logger.info("")
        logger.info("🧠 Loading voice recognition model...")
        logger.info("⏳ First run: Downloading model (~500MB, 2-5 minutes)")
        logger.info("⏳ Subsequent runs: Loading from cache (10-20 seconds)")
        
        voice_service = VoiceRecognitionService(
            model_name=Config.MODEL_NAME,
            model_save_dir=Config.MODEL_SAVE_DIR
        )
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ ALL SERVICES INITIALIZED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error(f"❌ SERVICE INITIALIZATION FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("💡 Common solutions:")
        logger.error("   1. Check .env file exists and has MONGODB_URI")
        logger.error("   2. Verify MongoDB Atlas connection")
        logger.error("   3. Check internet connection (for model download)")
        logger.error("   4. Ensure Python 3.11 (not 3.12)")
        logger.error("")
        return False


def register_blueprints():
    """Register all API blueprints"""
    try:
        logger.info("📋 Registering API routes...")
        
        # Initialize and register voice routes
        voice_bp = init_voice_routes(
            audio_processor=audio_processor,
            voice_service=voice_service,
            mongo_uri=Config.MONGODB_URI,
            db_name=Config.DATABASE_NAME,
            config=Config
        )
        
        app.register_blueprint(voice_bp)
        
        logger.info("✅ API routes registered")
        logger.info("   - POST /api/voice/register")
        logger.info("   - POST /api/voice/identify")
        logger.info("   - POST /api/voice/verify")
        logger.info("   - GET /api/voice/users")
        logger.info("   - DELETE /api/voice/users/<name>")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Blueprint registration failed: {e}")
        raise


if __name__ == '__main__':
    try:
        # Print banner
        print("")
        print("=" * 70)
        print("  🎤 VOICE RECOGNITION API SERVER")
        print("  Powered by SpeechBrain ECAPA-TDNN")
        print("=" * 70)
        print("")
        
        # Initialize services
        if not initialize_services():
            logger.error("❌ Failed to initialize services. Exiting.")
            sys.exit(1)
        
        # Register blueprints
        register_blueprints()
        
        # Print server info
        logger.info("=" * 70)
        logger.info("🌐 SERVER CONFIGURATION")
        logger.info("=" * 70)
        logger.info(f"🔗 URL: http://0.0.0.0:{Config.PORT}")
        logger.info(f"🔗 Local: http://localhost:{Config.PORT}")
        logger.info(f"🔗 Network: http://<YOUR_IP>:{Config.PORT}")
        logger.info(f"🔧 Debug mode: {Config.DEBUG}")
        logger.info(f"🎯 Similarity threshold: {Config.SIMILARITY_THRESHOLD}")
        logger.info("=" * 70)
        logger.info("")
        logger.info("💡 Server accessible from:")
        logger.info("   - Same computer: http://localhost:5000")
        logger.info("   - Other devices: http://<YOUR_IP>:5000")
        logger.info("   - Mobile app: Update IP in api_service.dart")
        logger.info("")
        logger.info("🔍 Health check: http://localhost:5000/health")
        logger.info("📚 API info: http://localhost:5000/")
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ SERVER READY - Waiting for requests...")
        logger.info("=" * 70)
        logger.info("")
        
        # Start Flask server
        app.run(
            host='0.0.0.0',  # Allow external connections (for mobile)
            port=Config.PORT,
            debug=Config.DEBUG,
            threaded=True  # Handle multiple requests
        )
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 70)
        logger.info("👋 Shutting down gracefully...")
        logger.info("=" * 70)
        logger.info("")
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ APPLICATION ERROR")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        import traceback
        traceback.print_exc()
        sys.exit(1)