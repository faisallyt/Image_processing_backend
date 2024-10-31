from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PIL import Image, ImageFilter
import pytesseract
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr_corrections = {
    "Oi": "Oil",
    "Potatc": "Potato",
    "0nion": "Onion",
}

def preprocess_image(image):
    """Preprocess the image for better OCR results"""
    try:
        # Convert to grayscale
        image = image.convert("L")
        # Apply median filter to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        # Sharpen the image
        image = image.filter(ImageFilter.SHARPEN)
        # Enhance contrast
        image = image.point(lambda x: 0 if x < 140 else 255)
        # Resize for better recognition
        image = image.resize((image.width * 3, image.height * 3), Image.LANCZOS)
        return image
    except Exception as e:
        logger.error(f"Error in image preprocessing: {str(e)}")
        raise

def split_combined_items(line):
    """Split items that are combined with '+' or ','"""
    # First replace '+' with ',' for uniform processing
    line = line.replace('+', ',')
    # Split by comma and clean each item
    items = [item.strip() for item in line.split(',')]
    # Filter out empty items
    items = [item for item in items if item]
    return items

def process_single_item(item_text):
    """Process a single item text to extract name and quantity"""
    # Clean the text
    item_text = re.sub(r'[^\w\s.]+', ' ', item_text).strip()
    
    if not item_text:
        return None
    
    # Match pattern for item name and quantity
    pattern = r"(\D+?)\s*(\d*\.?\d*\s*(?:kg|g|liters?|l|ml)?)?\s*$"
    match = re.match(pattern, item_text, re.IGNORECASE)
    
    if match:
        itemname, quantity = match.groups()
        
        # Clean and correct item name
        itemname = itemname.strip().title()
        itemname = ocr_corrections.get(itemname, itemname)
        
        # Clean quantity
        quantity = quantity.strip() if quantity else ""
        
        # Only return items with valid names
        if len(itemname) > 1:  # Avoid single-letter items
            return {
                "itemname": itemname,
                "quantity": quantity
            }
    return None

@app.post("/process-image")
async def process_image(file: UploadFile = File(...)):
    try:
        # Open and preprocess the image
        image = Image.open(file.file)
        processed_image = preprocess_image(image)
        
        # Fixed Tesseract configuration
        custom_config = '--oem 3 --psm 6'
        
        # Extract text
        extracted_text = pytesseract.image_to_string(
            processed_image,
            config=custom_config
        )
        
        logger.info("Raw Extracted Text:")
        logger.info(extracted_text)
        
        items = []
        
        # Process each line
        for line in extracted_text.splitlines():
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check if line contains separators (+ or ,)
            if '+' in line or ',' in line:
                combined_items = split_combined_items(line)
                for item in combined_items:
                    processed_item = process_single_item(item)
                    if processed_item:
                        items.append(processed_item)
            else:
                processed_item = process_single_item(line)
                if processed_item:
                    items.append(processed_item)
        
        logger.info("Processed Items:")
        logger.info(items)
        
        return {"items": items}
    
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise

# Optional: Add path to Tesseract if it's not in system PATH
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'