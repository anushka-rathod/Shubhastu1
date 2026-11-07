"""
Cloud image hosting service for Shubhashtu Fashion.
Enables cloud image storage (Cloudinary) to prevent any disk write errors
on serverless platforms like Vercel and AWS Lambda.
"""
import os
import time
import hmac
import hashlib
import base64
import logging
from config import Config

logger = logging.getLogger("shubhashtu.image_service")

class ImageService:
    @staticmethod
    def is_cloudinary_configured() -> bool:
        """Returns True if Cloudinary credentials are provided in Config or environment."""
        cloud_name = getattr(Config, 'CLOUDINARY_CLOUD_NAME', '') or os.environ.get('CLOUDINARY_CLOUD_NAME', '')
        api_key = getattr(Config, 'CLOUDINARY_API_KEY', '') or os.environ.get('CLOUDINARY_API_KEY', '')
        api_secret = getattr(Config, 'CLOUDINARY_API_SECRET', '') or os.environ.get('CLOUDINARY_API_SECRET', '')
        return bool(cloud_name and api_key and api_secret)

    @staticmethod
    def upload_image_bytes(file_bytes: bytes, filename: str = "product.jpg") -> dict:
        """
        Uploads image directly to Cloudinary REST API.
        Never touches the local filesystem, guaranteeing 100% compatibility with Vercel.
        """
        if not ImageService.is_cloudinary_configured():
            # If Cloudinary is not configured, encode as compressed data-URI fallback for test runs
            b64_data = base64.b64encode(file_bytes).decode('utf-8')
            mime = "image/jpeg"
            if filename.lower().endswith(".png"): mime = "image/png"
            elif filename.lower().endswith(".webp"): mime = "image/webp"
            return {
                'success': True,
                'configured': False,
                'url': f"data:{mime};base64,{b64_data}",
                'message': 'Image encoded as data-URI. Configure CLOUDINARY_CLOUD_NAME in .env for CDN hosting.'
            }

        try:
            import requests
            cloud_name = Config.CLOUDINARY_CLOUD_NAME
            api_key = Config.CLOUDINARY_API_KEY
            api_secret = Config.CLOUDINARY_API_SECRET
            timestamp = str(int(time.time()))

            # Generate Cloudinary API signature
            to_sign = f"folder=shubhashtu_products&timestamp={timestamp}{api_secret}"
            signature = hashlib.sha1(to_sign.encode('utf-8')).hexdigest()

            payload = {
                'api_key': api_key,
                'timestamp': timestamp,
                'folder': 'shubhashtu_products',
                'signature': signature
            }
            files = {
                'file': (filename, file_bytes, 'image/jpeg')
            }

            resp = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
                data=payload,
                files=files,
                timeout=15
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                secure_url = data.get('secure_url') or data.get('url')
                return {
                    'success': True,
                    'configured': True,
                    'url': secure_url
                }
            else:
                logger.error("Cloudinary upload failed: %s", resp.text)
                return {
                    'success': False,
                    'error': f"Cloudinary error: {resp.text}"
                }
        except Exception as e:
            logger.exception("Failed to upload image to Cloudinary: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

