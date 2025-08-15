#!/usr/bin/env python3
"""
Initialize models and NLTK data on first run
This script downloads models to cached volumes if they don't exist
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_huggingface_model():
    """Download HuggingFace model if not cached"""
    model_id = os.getenv('EMBEDDING_MODEL_ID', 'sentence-transformers/all-mpnet-base-v2')
    cache_dir = Path('/root/.cache/huggingface')
    
    # Check if model exists in cache
    model_cache_path = cache_dir / 'hub'
    if model_cache_path.exists() and any(model_cache_path.iterdir()):
        logger.info(f"✅ HuggingFace model {model_id} found in cache")
        return True
    
    logger.info(f"📥 Downloading HuggingFace model {model_id}...")
    try:
        os.system(f"huggingface-cli download {model_id} --repo-type model")
        logger.info(f"✅ Successfully downloaded {model_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to download {model_id}: {e}")
        return False

def download_nltk_data():
    """Download NLTK data if not cached"""
    nltk_dir = Path('/root/nltk_data')
    
    # Check if NLTK data exists
    if nltk_dir.exists() and any(nltk_dir.iterdir()):
        logger.info("✅ NLTK data found in cache")
        return True
    
    logger.info("📥 Downloading NLTK data...")
    try:
        import nltk
        nltk.download('punkt', download_dir='/root/nltk_data')
        nltk.download('punkt_tab', download_dir='/root/nltk_data')
        nltk.download('wordnet', download_dir='/root/nltk_data')
        nltk.download('omw-1.4', download_dir='/root/nltk_data')
        nltk.download('averaged_perceptron_tagger_eng', download_dir='/root/nltk_data')
        logger.info("✅ Successfully downloaded NLTK data")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to download NLTK data: {e}")
        return False

def main():
    """Initialize models and data"""
    logger.info("🚀 Initializing models and data...")
    
    success = True
    success &= download_huggingface_model()
    success &= download_nltk_data()
    
    if success:
        logger.info("✅ All models and data initialized successfully")
        sys.exit(0)
    else:
        logger.error("❌ Some downloads failed")
        sys.exit(1)

if __name__ == "__main__":
    main()