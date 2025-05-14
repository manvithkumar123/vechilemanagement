import logging
import random
import re
import os
import base64
import io
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

# Google Cloud Vision imports
from google.cloud import vision
from google.oauth2.service_account import Credentials
from google.cloud.vision_v1 import types
import google.auth
import json

def clean_plate_text(text):
    """
    Clean and format the detected license plate text
    
    Args:
        text: Raw text from OCR
        
    Returns:
        str: Cleaned plate number
    """
    if not text:
        return None
    
    # Remove newlines, extra spaces, and other noise
    text = re.sub(r'[\n\r\t]', ' ', text)
    text = re.sub(r'\s+', '', text)
    
    # Keep only alphanumeric characters
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Check if the text resembles an Indian license plate pattern
    # Common patterns: XX00XX0000 or XX00X0000
    plate_pattern = re.compile(r'^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}$')
    
    if plate_pattern.match(text):
        return text
    
    # Try to identify probable state codes
    state_codes = ['AP', 'TS', 'TN', 'KA', 'MH', 'DL', 'KL', 'UP', 'HR', 'GJ']
    
    # If text is too short or doesn't match the pattern, but contains digits and letters
    if len(text) >= 4 and re.search(r'[A-Z]', text) and re.search(r'[0-9]', text):
        # Check if first two chars could be a state code
        potential_state = text[:2]
        if potential_state in state_codes:
            # Preserve what we have as a reasonable approximation
            return text
        else:
            # If no recognizable state code, default to TS (Telangana)
            # and keep the rest of the text
            return f"TS{text}"
    
    return None

def detect_text_with_google_vision(image_path):
    """
    Use Google Cloud Vision API to detect text in an image
    
    Args:
        image_path: Path to the image file
        
    Returns:
        list: Detected text annotations
    """
    try:
        # Initialize Google Cloud Vision client
        # Using API key authentication
        api_key = os.environ.get("GOOGLE_VISION_API_KEY")
        if not api_key:
            logging.error("Google Vision API key not found in environment variables")
            return None
        
        # Read the image file
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        # Prepare the image for the API request
        image = {'content': content}
        
        # API endpoint directly (not using client library for API key auth)
        import requests
        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        payload = {
            "requests": [
                {
                    "image": {
                        "content": base64.b64encode(content).decode('utf-8')
                    },
                    "features": [
                        {
                            "type": "TEXT_DETECTION"
                        }
                    ]
                }
            ]
        }
        
        # Make the API request
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            logging.error(f"Google Vision API error: {response.text}")
            return None
            
        result = response.json()
        
        # Extract the text annotations
        if 'responses' in result and len(result['responses']) > 0:
            if 'textAnnotations' in result['responses'][0]:
                annotations = result['responses'][0]['textAnnotations']
                if annotations:
                    # First annotation is the entire text, subsequent ones are per word
                    detected_texts = [annotation['description'] for annotation in annotations]
                    return detected_texts
        
        logging.warning("No text annotations found in image")
        return None
        
    except Exception as e:
        logging.error(f"Error using Google Vision API: {str(e)}")
        return None

def analyze_image_for_plate(image_path):
    """
    Analyze the image using Google Vision API to find license plate
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Most likely license plate number or None
    """
    # Get all text detected in the image
    detected_texts = detect_text_with_google_vision(image_path)
    
    if not detected_texts:
        return None
    
    # Regular expression patterns for Indian license plates
    # Format: XX-00-XX-0000 or XX-00-X-0000 (with or without hyphens)
    patterns = [
        r'[A-Z]{2}\s*[0-9]{1,2}\s*[A-Z]{1,3}\s*[0-9]{1,4}',  # XX 00 XX 0000
        r'[A-Z]{2}\s*[0-9]{1,2}\s*[0-9]{1,4}',               # XX 00 0000 (missing letters)
        r'[A-Z]{2}\s*[0-9]{4,}'                              # XX 0000... (simplified)
    ]
    
    potential_plates = []
    
    # Check each detected text against license plate patterns
    for text in detected_texts:
        text = text.upper().strip()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            potential_plates.extend(matches)
    
    # Also check the entire first text (often contains the full image text)
    if detected_texts:
        full_text = detected_texts[0].upper().replace('\n', ' ')
        for pattern in patterns:
            matches = re.findall(pattern, full_text)
            potential_plates.extend(matches)
    
    # Clean the detected plates to a standard format
    cleaned_plates = []
    for plate in potential_plates:
        # Remove spaces and other non-alphanumeric characters
        cleaned = re.sub(r'[^A-Z0-9]', '', plate)
        if cleaned:
            cleaned_plates.append(cleaned)
    
    # If we have potential plates, return the most likely one
    if cleaned_plates:
        # Use the first one for now - it's often the most complete
        return cleaned_plates[0]
    
    return None

def process_image(image_path):
    """
    Process an image to extract vehicle license plate using Google Vision API
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Detected license plate text or a fallback
    """
    try:
        logging.info(f"Processing image from {image_path}")
        
        # Try to detect the license plate using Google Vision
        plate_number = analyze_image_for_plate(image_path)
        
        if plate_number:
            # Clean up the plate number
            plate_number = clean_plate_text(plate_number)
            if plate_number:
                logging.info(f"Google Vision detected plate: {plate_number}")
                return plate_number
        
        # If Google Vision fails, don't use fallback, just return None
        # This allows the frontend to display an editable default
        # that the user will need to correct manually
        logging.warning("Google Vision couldn't detect a valid plate, returning None")
        return None
        
    except Exception as e:
        logging.error(f"Error in image processing: {str(e)}")
        # Return None to let the frontend display a default
        return None
