import logging
import random
import re
import os
import base64
import io
import subprocess
import tempfile
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

# Explicitly set the Tesseract binary path
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# Initialize logging
logging.basicConfig(level=logging.INFO)

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

def enhance_image_for_ocr(image_path):
    """
    Enhance the image to improve OCR accuracy
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Path to the enhanced image
    """
    try:
        # Open the image
        img = Image.open(image_path)

        # Auto-invert if background is light and text is dark
        grayscale = img.convert('L')
        brightness = grayscale.resize((1, 1)).getpixel((0, 0))
        if brightness > 127:
            img = ImageOps.invert(grayscale)
        else:
            img = grayscale

        # Resize if needed
        if img.width > 1000 or img.height > 1000:
            img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)

        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Apply sharpening
        img = img.filter(ImageFilter.SHARPEN)

        # Apply thresholding to make it black and white
        threshold = 150  
        # We need to use a different approach for thresholding that doesn't involve comparison
        lut = [0] * threshold + [255] * (256 - threshold)
        img = img.point(lut)

        # Save to a temporary file
        enhanced_path = tempfile.mktemp(suffix='.png')
        img.save(enhanced_path)

        return enhanced_path
    
    except Exception as e:
        logging.error(f"Error enhancing image: {str(e)}")
        return image_path

def detect_text_with_tesseract(image_path):
    """
    Use Tesseract OCR to detect text in an image
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Detected text
    """
    try:
        # Enhance the image for better OCR results
        enhanced_image_path = enhance_image_for_ocr(image_path)
        
        # Run tesseract directly using subprocess
        # Configuring for license plate recognition:
        # --psm 7: Treat the image as a single line of text
        # --oem 1: Use LSTM OCR Engine
        cmd = [
            'tesseract',
            enhanced_image_path,
            'stdout',
            '--psm', '7',
            '-l', 'eng',
            '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
        ]
        
        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up the enhanced image if it's different from the original
        if enhanced_image_path != image_path:
            os.unlink(enhanced_image_path)
        
        # Check for errors
        if result.returncode != 0:
            logging.error(f"Tesseract error: {result.stderr}")
            
            # Try with a different PSM mode if the first one failed
            cmd = [
                'tesseract',
                image_path,
                'stdout',
                '--psm', '6',  # Assume a single uniform block of text
                '-l', 'eng'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return None
        
        # Get the detected text
        text = result.stdout.strip()
        
        return text
        
    except Exception as e:
        logging.error(f"Error using Tesseract OCR: {str(e)}")
        return None

def extract_plate_from_text(text):
    """
    Extract license plate numbers from detected text
    
    Args:
        text: Raw text from OCR
        
    Returns:
        str: Most likely license plate number or None
    """
    if not text:
        return None
    
    # Regular expression patterns for license plates
    # Format: XX-00-XX-0000 or XX-00-X-0000 (with or without hyphens)
    patterns = [
        r'[A-Z]{2}\s*[0-9]{1,2}\s*[A-Z]{1,3}\s*[0-9]{1,4}',  # XX 00 XX 0000
        r'[A-Z]{2}\s*[0-9]{1,2}\s*[0-9]{1,4}',               # XX 00 0000 (missing letters)
        r'[A-Z]{2}\s*[0-9]{4,}'                              # XX 0000... (simplified)
    ]
    
    # Check each pattern
    for pattern in patterns:
        matches = re.findall(pattern, text.upper())
        if matches:
            # Clean the first match
            cleaned = re.sub(r'[^A-Z0-9]', '', matches[0])
            if cleaned:
                return cleaned
    
    # If no valid plate pattern was found, try to extract any text that looks like it might be part of a plate
    # Look for 2 consecutive letters followed by numbers
    alphanum_pattern = r'[A-Z]{2,}[0-9]+'
    matches = re.findall(alphanum_pattern, text.upper())
    if matches:
        return matches[0]
    
    # As a last resort, return any alphanumeric sequence found
    alphanum = re.sub(r'[^A-Z0-9]', '', text.upper())
    if len(alphanum) >= 4:  # Only if it's long enough to be meaningful
        return alphanum
    
    return None

def try_multiple_ocr_methods(image_path):
    """
    Try multiple OCR methods to extract text from the image
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Detected license plate text or None
    """
    # First try with Tesseract
    try:
        # Try different PSM modes and configurations
        psm_modes = [7, 8, 6, 3]  # Different page segmentation modes
        
        for psm in psm_modes:
            # Enhance the image for better OCR results
            enhanced_image_path = enhance_image_for_ocr(image_path)
            
            cmd = [
                'tesseract',
                enhanced_image_path,
                'stdout',
                f'--psm', f'{psm}',
                '-l', 'eng',
                '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up the enhanced image
            if enhanced_image_path != image_path:
                os.unlink(enhanced_image_path)
            
            if result.returncode == 0:
                text = result.stdout.strip()
                if text:
                    # Extract plate from the text
                    plate = extract_plate_from_text(text)
                    if plate:
                        logging.info(f"Tesseract detected plate with PSM {psm}: {plate}")
                        return plate
    
    except Exception as e:
        logging.error(f"Error with multiple OCR methods: {str(e)}")
    
    return None

def process_image(image_path):
    """
    Process an image to extract vehicle license plate text
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Detected license plate text or None
    """
    try:
        logging.info(f"Processing image from {image_path}")
        
        # Try to detect the license plate using multiple OCR methods
        plate_number = try_multiple_ocr_methods(image_path)
        
        if plate_number:
            # Clean up the plate number
            plate_number = clean_plate_text(plate_number)
            if plate_number:
                logging.info(f"OCR detected plate: {plate_number}")
                return plate_number
        
        # Get actual text directly from the image to display
        # Even if it's not a perfect license plate format
        raw_text = detect_text_with_tesseract(image_path)
        if raw_text:
            # Clean and filter to just alphanumerics
            text = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
            if len(text) >= 4:  # If we have at least a few characters
                logging.info(f"Using raw detected text: {text}")
                return text
        
        # If all OCR attempts fail, return None to let the frontend display a default
        logging.warning("All OCR methods failed, returning None")
        return None
        
    except Exception as e:
        logging.error(f"Error in image processing: {str(e)}")
        return None
